

def format_large_number(value):
    if value is None or not isinstance(value, int):
        return value

    if abs(value) >= 1e9:
        # Format the number with commas for thousands separation
        formatted_value = f"{value/1e9:,.3f}".rstrip('0').rstrip('.')
        return f"{formatted_value} Billion"
    elif abs(value) >= 1e6:
        formatted_value = f"{value/1e6:,.3f}".rstrip('0').rstrip('.')
        return f"{formatted_value} Million"
    else:
        # No need for additional formatting
        return f"{value:,}"


def rounded_percentage(value):
    if value is None:
        return "nil"
    if value < 0:
        return f"-{round(float(value), 3)}"
    return f"+{round(float(value), 3)}"


def accounting_format(number):
    if number is None or number == 0:
        return "nil"
    if number > 0:
        return f"{number:,.2f}"
    return f"({-number:,.2f})"
