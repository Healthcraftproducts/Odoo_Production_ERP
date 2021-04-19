13.0.1 (Date : 19 feb 2020)
----------------------------
initial release

13.0.2 (Date : 20 feb 2020)
----------------------------
- Given Price Extra feature to add varient price at import time
  format:
  		attribute_value@attribute_price, attribute_value@attribute_price
  		
validate_field_text
validate_field_integer
validate_field_float
validate_field_char
validate_field_boolean
validate_field_selection
validate_field_many2one
validate_field_many2many  		

13.0.3
- ADDED CREATE OR WRITE PRODUCT VARIANTS
- ADDED DYNAMIC IMPORT FIELDS.


13.0.4(11 MARCH 2020)
=====================
- FIXED ISSUE WHEN WHEN TWO DIFFERENT ATTRIBUTE HAS SAME VALUE.
- CODE MODIFIED IN SEARCH QUERY.
attr_value_ids_list = []
if len(attr_ids_list) == len(attr_value_list):
    i = 0
    while i < len(attr_ids_list):
        search_attr_value = False
        search_attr_value = pro_attr_value_obj.search([
            ('name','=',attr_value_list[i]),
            ('attribute_id','=',attr_ids_list[i] )
            ], limit = 1)
            
            
==> remove attribute or attribute line and attribute value sequence changed.
1) First remove attribute or line 
2) then, remove attribute value.           
in order to fix below issue:
The attribute Rellenable99 must have at least one value for the product Electrodo Redox/ORP IntelliCAL.

=================================


