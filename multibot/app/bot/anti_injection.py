import re

# Patterns that indicate prompt injection or role manipulation attempts
_INJECTION_PATTERNS = [
    r"ignora\s*(\w+\s*)?(instrucciones|reglas|comandos|restricciones)",
    r"ignore\s*(\w+\s*)?(instructions|rules|commands|restrictions)",
    r"olvida\s*(\w+\s*)?(instrucciones|reglas|comandos|restricciones)",
    r"forget\s*(\w+\s*)?(instructions|rules|commands|restrictions)",
    r"actúa\s*como\s*(si\s*fueras|un)",
    r"act\s*as\s*(if\s*you\s*(were|are)|a)",
    r"eres\s*(ahora\s*)?(un|una|el|la)\s*(bot|robot|asistente|ia|inteligencia)",
    r"you\s*are\s*now\s*a\s*(different|new|other)?\s*(bot|robot|assistant|ai|system)",
    r"(dime|muéstrame|revela)\s*(tu|el|los?)\s*(prompt|system\s*prompt|instrucciones\s*del\s*sistema)",
    r"(tell|show|reveal)\s*(me\s*)?(your\s*)?(prompt|system\s*prompt|instructions)",
    r"jailbreak",
    r"DAN\s*mode",
    r"modo\s*DAN",
    r"<\s*system\s*>",
    r"\[INST\]",
    r"<<SYS>>",
    r"print\s*\(\s*['\"]",
    r"import\s+(os|sys|subprocess)",
    r"(ejecuta|run|exec)\s*\(",
    r"base64\s*\.",
    r"desactiva\s*(tu\s*)?(filtro|censura|restricci[oó]n)",
    r"disable\s*(your\s*)?(filter|censorship|restriction)",
    r"pretend\s*(you\s*are|to\s*be)",
    r"finge\s*(ser|que\s*eres)",
    r"en\s*este\s*(escenario|contexto)\s*eres",
    r"for\s*this\s*(scenario|context)\s*you\s*are",
]

_COMPILED = [re.compile(p, re.IGNORECASE | re.UNICODE) for p in _INJECTION_PATTERNS]


def check_injection(text: str) -> bool:
    """Return True if the text looks like a prompt injection attempt."""
    for pattern in _COMPILED:
        if pattern.search(text):
            return True
    return False
