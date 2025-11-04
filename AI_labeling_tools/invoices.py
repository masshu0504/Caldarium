

#invoices
import Label_invoices_NER


invoice_formatting = "{invoice_number:{type:string},patient_id:{type:string},invoice_date:{type:string,format:YYYY-MM-DD},due_date:{type:string,format:YYYY-MM-DD},patient_name:{type:string},patient_age:{type:number},patient_address:{type:string,help:Patient mailing address NOT hospital address},patient_phone:{type:string,format:x-xxx-xxx-xxxx,help:Patient phone number NOT HOSPITAL PHONE},patient_email:{type:string,help:Patient email address NOT EMAIL OF HOSPITAL},admission_date:{type:string,format:YYYY-MM-DD},discharge_date:{type:string,format:YYYY-MM-DD},subtotal_amount:{type:number|null},discount_amount:{type:number|null},total_amount:{type:number},provider_name:{type:string,help:Name of the Doctor NOT THE NAME OF THE HOSPITAL},bed_id:{type:string},line_items:{description:{type:string},code:{type:string},amount:{type:number}}}"
system_prompt = "You are performing NER labeling on invoices. Extract the following fields in strict JSON format (no text outside JSON): " + invoice_formatting +". If a field is missing, set it to null. Use Common Sense when filling fields, for example info@whitepetalhospital.org would NOT be the patient email as it is clearly a hospital email. an unlabelled phone in the body of the invoice is usally a personal phone, a way to tell this is patent info is usally close to other patient info"


Label_invoices_NER.parse(system_prompt,"input_invoices","output_invoices","output_audit.txt")