"""Tokyo Night theme definition for omoduo in Omarchy."""

TOKYO_NIGHT = {
    "bg": "#1a1b26",
    "surface": "#16161e",
    "panel": "#1f2335",
    "border": "#292e42",
    "border_focus": "#7aa2f7",
    "fg": "#c0caf5",
    "fg_dim": "#565f89",
    "claude_accent": "#ff9e64",
    "claude_header": "#e0af68",
    "agy_accent": "#7dcfff",
    "agy_header": "#7aa2f7",
    "user_accent": "#bb9af7",
    "success": "#9ece6a",
    "warning": "#e0af68",
    "error": "#f7768e",
}

APP_CSS = f"""
Screen {{
    background: {TOKYO_NIGHT["bg"]};
    color: {TOKYO_NIGHT["fg"]};
}}

#header-bar {{
    dock: top;
    height: 1;
    background: {TOKYO_NIGHT["surface"]};
    color: {TOKYO_NIGHT["fg_dim"]};
    padding: 0 1;
}}

#main-container {{
    layout: horizontal;
    height: 1fr;
    width: 100%;
}}

.work-pane {{
    width: 28%;
    height: 100%;
    background: {TOKYO_NIGHT["surface"]};
    border: solid {TOKYO_NIGHT["border"]};
    padding: 0 1;
}}

.work-pane:focus {{
    border: solid {TOKYO_NIGHT["border_focus"]};
}}

#claude-pane {{
    border-title-color: {TOKYO_NIGHT["claude_header"]};
}}

#agy-pane {{
    border-title-color: {TOKYO_NIGHT["agy_header"]};
}}

#conversation-pane {{
    width: 44%;
    height: 100%;
    background: {TOKYO_NIGHT["bg"]};
    border: double {TOKYO_NIGHT["border"]};
    padding: 0 1;
}}

#conversation-pane:focus {{
    border: double {TOKYO_NIGHT["border_focus"]};
}}

#conversation-log {{
    height: 1fr;
    scrollbar-size: 1 1;
}}

#input-box {{
    dock: bottom;
    height: 3;
    border: tall {TOKYO_NIGHT["border"]};
    background: {TOKYO_NIGHT["surface"]};
    color: {TOKYO_NIGHT["fg"]};
    padding: 0 1;
}}

#input-box:focus {{
    border: tall {TOKYO_NIGHT["border_focus"]};
}}

#status-bar {{
    dock: bottom;
    height: 1;
    background: {TOKYO_NIGHT["surface"]};
    color: {TOKYO_NIGHT["fg_dim"]};
    padding: 0 1;
}}
"""
