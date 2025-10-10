from app.utils.template_filters import format_number_eu, format_decimal_eu

print('Test filtros:')
print('200.0000 ->', format_number_eu(200.0000))
print('8.66 ->', format_decimal_eu(8.66, 2))
print('1732.00 ->', format_decimal_eu(1732.00, 2))
print('4000.0 ->', format_number_eu(4000.0))
print('37000.0 ->', format_number_eu(37000.0))

