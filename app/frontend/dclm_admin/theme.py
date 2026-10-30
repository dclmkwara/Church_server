from faststrap import create_theme, set_component_defaults


DCLM_THEME = create_theme(
    primary="#0F2D5E",
    secondary="#1D4ED8",
    success="#059669",
    danger="#DC2626",
    warning="#D97706",
    info="#7C3AED",
    light="#F1F5F9",
    dark="#0F172A",
)


def setup_theme_defaults() -> None:
    set_component_defaults("Button", variant="primary", size="md", css_vars={"--bs-btn-border-radius": "6px"})
    set_component_defaults("Badge", pill=True)
    set_component_defaults("Card", shadow="sm", border=False, css_vars={"--bs-card-border-radius": "10px"})
    set_component_defaults("Alert", dismissible=True)
    set_component_defaults("Drawer", placement="end", css_vars={"--bs-offcanvas-border-radius": "12px"})
    set_component_defaults("Modal", centered=True, css_vars={"--bs-modal-border-radius": "12px"})
    set_component_defaults("ModernToast", duration=3500, position="top-end", style="glass")
    set_component_defaults("ModernToastStack", position="top-end")
    set_component_defaults("Table", hover=True, striped=True)
    set_component_defaults("Spinner", variant="primary", size="sm")
