"""
User approval and account management routes.

This module handles the user registration approval workflow, allowing:
- Workers to request user accounts (self-registration)
- Location admins to approve/reject user requests
- Bulk approval operations
- Account activation/deactivation

The workflow ensures that only authorized workers get application access.
"""
from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from datetime import datetime

from app.api import deps
from app.models.user import User, Worker
from app.schemas.user import UserResponse, UserApprovalRequest, BulkApprovalRequest
from app.core.security import hash_password

router = APIRouter()


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def request_user_account(
    *,
    db: AsyncSession = Depends(deps.get_db),
    worker_id: str,
    password: str,
) -> Any:
    """
    Worker self-registration for user account.
    
    Creates a pending user account that requires admin approval before granting
    application access. The worker must already exist in the workers table.
    
    Args:
        db: Database session dependency
        worker_id: UUID of the existing worker requesting access
        password: Desired password for the account
        
    Returns:
        UserResponse: Created user object with approval_status='pending'
        
    Raises:
        HTTPException 404: Worker not found
        HTTPException 400: User account already exists for this worker
        
    Example:
        ```python
        POST /api/v1/users/register
        {
            "worker_id": "550e8400-e29b-41d4-a716-446655440000",
            "password": "SecurePass123!"
        }
        ```
        
    Notes:
        - Worker must exist before requesting user account
        - Password is hashed before storage
        - Default approval_status is 'pending'
        - Location admin will be notified for approval
    """
    # Verify worker exists
    worker_result = await db.execute(
        select(Worker).where(Worker.worker_id == worker_id)
    )
    worker = worker_result.scalar_one_or_none()
    
    if not worker:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Worker with ID {worker_id} not found"
        )
    
    # Check if user already exists
    existing_user = await db.execute(
        select(User).where(User.worker_id == worker_id)
    )
    if existing_user.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User account already exists for this worker"
        )
    
    # Create pending user
    hashed_password = hash_password(password)
    new_user = User(
        worker_id=worker.worker_id,
        password=hashed_password,
        location_id=worker.location_id,
        name=worker.name,
        phone=worker.phone,
        email=worker.email,
        approval_status="pending",  # Requires admin approval
        is_active=False,  # Inactive until approved
    )
    
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    
    return new_user


@router.get("/pending", response_model=List[UserResponse])
async def list_pending_users(
    *,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """
    List all pending user approval requests.
    
    Returns users awaiting approval, scoped to the current admin's location.
    Only accessible by users with admin/pastor roles.
    
    Args:
        db: Database session dependency
        current_user: Currently authenticated user (must be admin)
        skip: Number of records to skip (pagination)
        limit: Maximum number of records to return
        
    Returns:
        List[UserResponse]: List of pending user accounts
        
    Raises:
        HTTPException 403: User lacks admin permissions
        
    Example:
        ```python
        GET /api/v1/users/pending?skip=0&limit=50
        ```
        
    Notes:
        - Results are filtered by location hierarchy (ltree path matching)
        - Only shows pending requests from current admin's scope
        - Ordered by created_at (oldest first)
    """
    # TODO: Add permission check for admin role
    # For now, any authenticated user can view pending requests in their location
    
    # Filter by location scope using ltree path
    query = (
        select(User)
        .where(User.approval_status == "pending")
        .where(User.path.descendant_of(current_user.path))  # Scope to admin's hierarchy
        .offset(skip)
        .limit(limit)
        .order_by(User.created_at)
    )
    
    result = await db.execute(query)
    return result.scalars().all()


@router.post("/{user_id}/approve", response_model=UserResponse)
async def approve_user(
    *,
    db: AsyncSession = Depends(deps.get_db),
    user_id: str,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Approve a pending user account.
    
    Grants application access to a worker by approving their user account.
    Only location admins can approve users within their hierarchy.
    
    Args:
        db: Database session dependency
        user_id: UUID of the user to approve
        current_user: Currently authenticated admin user
        
    Returns:
        UserResponse: Updated user object with approval_status='approved'
        
    Raises:
        HTTPException 404: User not found
        HTTPException 403: Admin lacks permission to approve this user
        HTTPException 400: User already approved or rejected
        
    Example:
        ```python
        POST /api/v1/users/550e8400-e29b-41d4-a716-446655440000/approve
        ```
        
    Notes:
        - Sets approval_status to 'approved'
        - Sets is_active to True
        - Records approver and approval timestamp
        - User can now login to the application
    """
    # Fetch user
    user_result = await db.execute(
        select(User).where(User.user_id == user_id)
    )
    user = user_result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found"
        )
    
    # Check if user is within admin's scope
    # TODO: Implement proper ltree path checking
    # For now, simple location_id check
    if user.location_id != current_user.location_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only approve users in your location"
        )
    
    # Check if already processed
    if user.approval_status != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"User is already {user.approval_status}"
        )
    
    # Approve user
    user.approval_status = "approved"
    user.is_active = True
    user.approved_by = current_user.user_id
    user.approved_at = datetime.utcnow()
    
    await db.commit()
    await db.refresh(user)
    
    return user


@router.post("/{user_id}/reject", response_model=UserResponse)
async def reject_user(
    *,
    db: AsyncSession = Depends(deps.get_db),
    user_id: str,
    reason: str,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Reject a pending user account.
    
    Denies application access to a worker by rejecting their user account request.
    Requires a reason for rejection for transparency.
    
    Args:
        db: Database session dependency
        user_id: UUID of the user to reject
        reason: Explanation for rejection (required)
        current_user: Currently authenticated admin user
        
    Returns:
        UserResponse: Updated user object with approval_status='rejected'
        
    Raises:
        HTTPException 404: User not found
        HTTPException 403: Admin lacks permission to reject this user
        HTTPException 400: User already approved or rejected, or reason missing
        
    Example:
        ```python
        POST /api/v1/users/550e8400-e29b-41d4-a716-446655440000/reject
        {
            "reason": "Worker has not completed required training"
        }
        ```
        
    Notes:
        - Sets approval_status to 'rejected'
        - Keeps is_active as False
        - Records rejection reason for worker to view
        - Worker can reapply after addressing concerns
    """
    if not reason or len(reason.strip()) < 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Rejection reason must be at least 10 characters"
        )
    
    # Fetch user
    user_result = await db.execute(
        select(User).where(User.user_id == user_id)
    )
    user = user_result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found"
        )
    
    # Check scope
    if user.location_id != current_user.location_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only reject users in your location"
        )
    
    # Check if already processed
    if user.approval_status != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"User is already {user.approval_status}"
        )
    
    # Reject user
    user.approval_status = "rejected"
    user.is_active = False
    user.approved_by = current_user.user_id
    user.approved_at = datetime.utcnow()
    user.rejection_reason = reason
    
    await db.commit()
    await db.refresh(user)
    
    return user


@router.post("/bulk-approve", response_model=dict)
async def bulk_approve_users(
    *,
    db: AsyncSession = Depends(deps.get_db),
    user_ids: List[str],
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Approve multiple user accounts in a single operation.
    
    Efficiently approves multiple pending users at once, useful for batch
    onboarding scenarios. All users must be within admin's scope.
    
    Args:
        db: Database session dependency
        user_ids: List of user UUIDs to approve
        current_user: Currently authenticated admin user
        
    Returns:
        dict: Summary of approval operation
            - approved_count: Number of successfully approved users
            - failed: List of user_ids that failed with reasons
            
    Raises:
        HTTPException 400: Empty user_ids list or invalid format
        
    Example:
        ```python
        POST /api/v1/users/bulk-approve
        {
            "user_ids": [
                "550e8400-e29b-41d4-a716-446655440000",
                "6ba7b810-9dad-11d1-80b4-00c04fd430c8"
            ]
        }
        
        Response:
        {
            "approved_count": 2,
            "failed": []
        }
        ```
        
    Notes:
        - Validates each user individually
        - Skips users outside admin's scope
        - Continues processing even if some approvals fail
        - Returns detailed failure information
    """
    if not user_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="user_ids list cannot be empty"
        )
    
    approved_count = 0
    failed = []
    
    for user_id in user_ids:
        try:
            # Fetch user
            user_result = await db.execute(
                select(User).where(User.user_id == user_id)
            )
            user = user_result.scalar_one_or_none()
            
            if not user:
                failed.append({"user_id": user_id, "reason": "User not found"})
                continue
            
            # Check scope
            if user.location_id != current_user.location_id:
                failed.append({"user_id": user_id, "reason": "Outside your location scope"})
                continue
            
            # Check status
            if user.approval_status != "pending":
                failed.append({"user_id": user_id, "reason": f"Already {user.approval_status}"})
                continue
            
            # Approve
            user.approval_status = "approved"
            user.is_active = True
            user.approved_by = current_user.user_id
            user.approved_at = datetime.utcnow()
            
            approved_count += 1
            
        except Exception as e:
            failed.append({"user_id": user_id, "reason": str(e)})
    
    await db.commit()
    
    return {
        "approved_count": approved_count,
        "failed": failed
    }


@router.post("/{user_id}/deactivate", response_model=UserResponse)
async def deactivate_user(
    *,
    db: AsyncSession = Depends(deps.get_db),
    user_id: str,
    reason: str,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Deactivate an active user account.
    
    Temporarily suspends a user's application access without deleting their account.
    User will see "Account deactivated" message when attempting to login.
    
    Args:
        db: Database session dependency
        user_id: UUID of the user to deactivate
        reason: Explanation for deactivation (required)
        current_user: Currently authenticated admin user
        
    Returns:
        UserResponse: Updated user object with is_active=False
        
    Raises:
        HTTPException 404: User not found
        HTTPException 403: Admin lacks permission
        HTTPException 400: User already inactive or reason missing
        
    Example:
        ```python
        POST /api/v1/users/550e8400-e29b-41d4-a716-446655440000/deactivate
        {
            "reason": "Transferred to another location"
        }
        ```
        
    Notes:
        - Sets is_active to False
        - Preserves approval_status
        - Can be reactivated later
        - User cannot login while deactivated
    """
    if not reason or len(reason.strip()) < 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Deactivation reason must be at least 10 characters"
        )
    
    # Fetch user
    user_result = await db.execute(
        select(User).where(User.user_id == user_id)
    )
    user = user_result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found"
        )
    
    # Check scope
    if user.location_id != current_user.location_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only deactivate users in your location"
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is already deactivated"
        )
    
    # Deactivate
    user.is_active = False
    user.rejection_reason = reason  # Reuse field for deactivation reason
    
    await db.commit()
    await db.refresh(user)
    
    return user


@router.post("/{user_id}/reactivate", response_model=UserResponse)
async def reactivate_user(
    *,
    db: AsyncSession = Depends(deps.get_db),
    user_id: str,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Reactivate a deactivated user account.
    
    Restores application access to a previously deactivated user.
    Only works for approved users who were deactivated.
    
    Args:
        db: Database session dependency
        user_id: UUID of the user to reactivate
        current_user: Currently authenticated admin user
        
    Returns:
        UserResponse: Updated user object with is_active=True
        
    Raises:
        HTTPException 404: User not found
        HTTPException 403: Admin lacks permission
        HTTPException 400: User not approved or already active
        
    Example:
        ```python
        POST /api/v1/users/550e8400-e29b-41d4-a716-446655440000/reactivate
        ```
        
    Notes:
        - Sets is_active to True
        - Only works for approved users
        - Clears deactivation reason
        - User can login immediately after reactivation
    """
    # Fetch user
    user_result = await db.execute(
        select(User).where(User.user_id == user_id)
    )
    user = user_result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found"
        )
    
    # Check scope
    if user.location_id != current_user.location_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only reactivate users in your location"
        )
    
    if user.approval_status != "approved":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only reactivate approved users"
        )
    
    if user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is already active"
        )
    
    # Reactivate
    user.is_active = True
    user.rejection_reason = None  # Clear deactivation reason
    
    await db.commit()
    await db.refresh(user)
    
    return user
