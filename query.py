-- Connect to the finance_agent database
\c finance_agent;

-- Clear existing data if needed
-- TRUNCATE TABLE journal_entry_lines CASCADE;
-- TRUNCATE TABLE journal_entries CASCADE;
-- TRUNCATE TABLE ar_invoice_payments CASCADE;
-- TRUNCATE TABLE ar_payments CASCADE;
-- TRUNCATE TABLE ar_invoice_items CASCADE;
-- TRUNCATE TABLE ar_invoices CASCADE;
-- TRUNCATE TABLE ap_invoice_payments CASCADE;
-- TRUNCATE TABLE ap_payments CASCADE;
-- TRUNCATE TABLE ap_invoice_items CASCADE;
-- TRUNCATE TABLE ap_invoices CASCADE;
-- TRUNCATE TABLE customers CASCADE;
-- TRUNCATE TABLE vendors CASCADE;
-- TRUNCATE TABLE account_balances CASCADE;
-- TRUNCATE TABLE fiscal_periods CASCADE;
-- TRUNCATE TABLE accounts CASCADE;

-- 1. Create Fiscal Period
INSERT INTO fiscal_periods (id, name, start_date, end_date, is_closed)
VALUES 
(gen_random_uuid(), 'FY2025', '2025-01-01', '2025-12-31', false);

-- 2. Create Chart of Accounts

-- Asset Accounts
INSERT INTO accounts (id, code, name, description, account_type, is_active, currency_code)
VALUES
-- Top-level account
(gen_random_uuid(), '1000', 'Assets', 'Asset accounts', 'ASSET', true, 'SAR'),
-- Cash accounts
(gen_random_uuid(), '1100', 'Cash and Cash Equivalents', 'Cash and liquid assets', 'ASSET', true, 'SAR'),
(gen_random_uuid(), '1101', 'Main Operating Account', 'Primary business checking account', 'ASSET', true, 'SAR'),
(gen_random_uuid(), '1102', 'Petty Cash', 'Small cash on hand', 'ASSET', true, 'SAR'),
-- Accounts Receivable
(gen_random_uuid(), '1200', 'Accounts Receivable', 'Amounts owed by customers', 'ASSET', true, 'SAR'),
-- Inventory
(gen_random_uuid(), '1300', 'Inventory', 'Goods held for sale', 'ASSET', true, 'SAR'),
-- Fixed Assets
(gen_random_uuid(), '1500', 'Fixed Assets', 'Long-term tangible assets', 'ASSET', true, 'SAR'),
(gen_random_uuid(), '1510', 'Equipment', 'Office and business equipment', 'ASSET', true, 'SAR'),
(gen_random_uuid(), '1600', 'Accumulated Depreciation', 'Accumulated depreciation of assets', 'ASSET', true, 'SAR'),
(gen_random_uuid(), '1610', 'Accumulated Depreciation - Equipment', 'Accumulated depreciation of equipment', 'ASSET', true, 'SAR');

-- Liability Accounts
INSERT INTO accounts (id, code, name, description, account_type, is_active, currency_code)
VALUES
-- Top-level account
(gen_random_uuid(), '2000', 'Liabilities', 'Liability accounts', 'LIABILITY', true, 'SAR'),
-- Current Liabilities
(gen_random_uuid(), '2100', 'Accounts Payable', 'Amounts owed to vendors', 'LIABILITY', true, 'SAR'),
(gen_random_uuid(), '2200', 'Salaries Payable', 'Amounts owed to employees', 'LIABILITY', true, 'SAR'),
(gen_random_uuid(), '2300', 'Taxes Payable', 'Taxes owed to authorities', 'LIABILITY', true, 'SAR'),
-- Long-term Liabilities
(gen_random_uuid(), '2500', 'Long-Term Loans', 'Loans due beyond one year', 'LIABILITY', true, 'SAR');

-- Equity Accounts
INSERT INTO accounts (id, code, name, description, account_type, is_active, currency_code)
VALUES
-- Top-level account
(gen_random_uuid(), '3000', 'Equity', 'Equity accounts', 'EQUITY', true, 'SAR'),
(gen_random_uuid(), '3100', 'Share Capital', 'Owner investments', 'EQUITY', true, 'SAR'),
(gen_random_uuid(), '3200', 'Retained Earnings', 'Accumulated earnings', 'EQUITY', true, 'SAR');

-- Revenue Accounts
INSERT INTO accounts (id, code, name, description, account_type, is_active, currency_code)
VALUES
-- Top-level account
(gen_random_uuid(), '4000', 'Revenue', 'Revenue accounts', 'REVENUE', true, 'SAR'),
(gen_random_uuid(), '4100', 'Sales Revenue', 'Revenue from sales', 'REVENUE', true, 'SAR'),
(gen_random_uuid(), '4200', 'Service Revenue', 'Revenue from services', 'REVENUE', true, 'SAR'),
(gen_random_uuid(), '4300', 'Interest Income', 'Revenue from interest', 'REVENUE', true, 'SAR');

-- Expense Accounts
INSERT INTO accounts (id, code, name, description, account_type, is_active, currency_code)
VALUES
-- Top-level account
(gen_random_uuid(), '5000', 'Cost of Goods Sold', 'Direct costs of products sold', 'EXPENSE', true, 'SAR'),
(gen_random_uuid(), '6000', 'Operating Expenses', 'Day-to-day expenses', 'EXPENSE', true, 'SAR'),
(gen_random_uuid(), '6100', 'Salaries Expense', 'Employee salaries', 'EXPENSE', true, 'SAR'),
(gen_random_uuid(), '6200', 'Rent Expense', 'Office rent', 'EXPENSE', true, 'SAR'),
(gen_random_uuid(), '6300', 'Utilities Expense', 'Electricity, water, etc.', 'EXPENSE', true, 'SAR'),
(gen_random_uuid(), '6400', 'Office Supplies', 'Office consumables', 'EXPENSE', true, 'SAR'),
(gen_random_uuid(), '6700', 'Depreciation Expense', 'Depreciation of assets', 'EXPENSE', true, 'SAR');

-- Set up account hierarchy (parent_id relationships)
-- Store account IDs in variables for reference
DO $$
DECLARE
    assets_id UUID;
    cash_id UUID;
    fixed_assets_id UUID;
    accum_dep_id UUID;
    liabilities_id UUID;
    equity_id UUID;
    revenue_id UUID;
    expenses_id UUID;
BEGIN
    -- Get primary account IDs
    SELECT id INTO assets_id FROM accounts WHERE code = '1000';
    SELECT id INTO cash_id FROM accounts WHERE code = '1100';
    SELECT id INTO fixed_assets_id FROM accounts WHERE code = '1500';
    SELECT id INTO accum_dep_id FROM accounts WHERE code = '1600';
    SELECT id INTO liabilities_id FROM accounts WHERE code = '2000';
    SELECT id INTO equity_id FROM accounts WHERE code = '3000';
    SELECT id INTO revenue_id FROM accounts WHERE code = '4000';
    SELECT id INTO expenses_id FROM accounts WHERE code = '5000';
    
    -- Update parent IDs for top-level categories
    UPDATE accounts SET parent_id = assets_id WHERE code LIKE '1%' AND code != '1000';
    UPDATE accounts SET parent_id = liabilities_id WHERE code LIKE '2%' AND code != '2000';
    UPDATE accounts SET parent_id = equity_id WHERE code LIKE '3%' AND code != '3000';
    UPDATE accounts SET parent_id = revenue_id WHERE code LIKE '4%' AND code != '4000';
    UPDATE accounts SET parent_id = expenses_id WHERE code IN ('6000');
    
    -- Update parent IDs for subcategories
    UPDATE accounts SET parent_id = cash_id WHERE code IN ('1101', '1102');
    UPDATE accounts SET parent_id = fixed_assets_id WHERE code = '1510';
    UPDATE accounts SET parent_id = accum_dep_id WHERE code = '1610';
    UPDATE accounts SET parent_id = (SELECT id FROM accounts WHERE code = '6000') WHERE code LIKE '6%' AND code != '6000';
END;
$$;

-- 3. Create Vendors and Customers

-- Vendors
INSERT INTO vendors (id, code, name, tax_id, contact_name, email, phone, address, status, payment_terms, account_id)
VALUES 
(
    gen_random_uuid(), 
    'V001', 
    'Office Supplies Co.', 
    '300123456700003', 
    'Ahmed Ali', 
    'ahmed@officesupplies.com', 
    '966512345678', 
    'Riyadh, Saudi Arabia', 
    'ACTIVE', 
    30, 
    (SELECT id FROM accounts WHERE code = '2100')
),
(
    gen_random_uuid(), 
    'V002', 
    'Tech Solutions Ltd.', 
    '310987654300008', 
    'Mohammed Hassan', 
    'mohammed@techsolutions.com', 
    '966523456789', 
    'Jeddah, Saudi Arabia', 
    'ACTIVE', 
    30, 
    (SELECT id FROM accounts WHERE code = '2100')
);

-- Customers
INSERT INTO customers (id, code, name, tax_id, contact_name, email, phone, address, status, payment_terms, credit_limit, account_id)
VALUES 
(
    gen_random_uuid(), 
    'C001', 
    'Saudi Trading Company', 
    '310729384500001', 
    'Fahad Al-Saud', 
    'fahad@stc.com', 
    '966545678901', 
    'Riyadh, Saudi Arabia', 
    'ACTIVE', 
    30, 
    100000.00, 
    (SELECT id FROM accounts WHERE code = '1200')
),
(
    gen_random_uuid(), 
    'C002', 
    'Gulf Industries', 
    '300234567800007', 
    'Khalid Al-Najm', 
    'khalid@gulf-industries.com', 
    '966556789012', 
    'Dammam, Saudi Arabia', 
    'ACTIVE', 
    30, 
    200000.00, 
    (SELECT id FROM accounts WHERE code = '1200')
);

-- 4. Create Journal Entries for Initial Setup

-- Initial Capital
INSERT INTO journal_entries (id, entry_number, entry_date, description, reference, status, is_recurring, created_by, created_at)
VALUES (
    gen_random_uuid(),
    'JE-20250101-INIT',
    '2025-01-01',
    'Initial capital contribution',
    'INIT-001',
    'POSTED',
    false,
    'admin',
    CURRENT_TIMESTAMP
);

-- Get the journal entry ID
DO $$
DECLARE
    je_id UUID;
BEGIN
    SELECT id INTO je_id FROM journal_entries WHERE entry_number = 'JE-20250101-INIT';
    
    -- Add journal entry lines
    INSERT INTO journal_entry_lines (id, journal_entry_id, account_id, description, debit_amount, credit_amount)
    VALUES 
    (
        gen_random_uuid(),
        je_id,
        (SELECT id FROM accounts WHERE code = '1101'), -- Main Operating Account
        'Initial capital',
        500000.00,
        0.00
    ),
    (
        gen_random_uuid(),
        je_id,
        (SELECT id FROM accounts WHERE code = '3100'), -- Share Capital
        'Initial capital',
        0.00,
        500000.00
    );
END;
$$;

-- Equipment Purchase
INSERT INTO journal_entries (id, entry_number, entry_date, description, reference, status, is_recurring, created_by, created_at)
VALUES (
    gen_random_uuid(),
    'JE-20250105-EQUIP',
    '2025-01-05',
    'Purchase of office equipment',
    'PO-001',
    'POSTED',
    false,
    'admin',
    CURRENT_TIMESTAMP
);

-- Get the journal entry ID
DO $$
DECLARE
    je_id UUID;
BEGIN
    SELECT id INTO je_id FROM journal_entries WHERE entry_number = 'JE-20250105-EQUIP';
    
    -- Add journal entry lines
    INSERT INTO journal_entry_lines (id, journal_entry_id, account_id, description, debit_amount, credit_amount)
    VALUES 
    (
        gen_random_uuid(),
        je_id,
        (SELECT id FROM accounts WHERE code = '1510'), -- Equipment
        'Office equipment purchase',
        50000.00,
        0.00
    ),
    (
        gen_random_uuid(),
        je_id,
        (SELECT id FROM accounts WHERE code = '1101'), -- Main Operating Account
        'Payment for equipment',
        0.00,
        50000.00
    );
END;
$$;

-- 5. Create AP Invoices

-- Office Supplies Invoice
INSERT INTO ap_invoices (id, invoice_number, vendor_id, vendor_invoice_number, issue_date, due_date, 
                         description, subtotal, tax_amount, total_amount, paid_amount, status, currency_code, 
                         created_by, created_at)
VALUES (
    gen_random_uuid(),
    'AP-INV-20250110-001',
    (SELECT id FROM vendors WHERE code = 'V001'),
    'OS-12345',
    '2025-01-10',
    '2025-02-09',
    'Office supplies purchase',
    5000.00,
    750.00,
    5750.00,
    5750.00,  -- Fully paid
    'PAID',
    'SAR',
    'admin',
    CURRENT_TIMESTAMP
);

-- Get the invoice ID
DO $$
DECLARE
    inv_id UUID;
BEGIN
    SELECT id INTO inv_id FROM ap_invoices WHERE invoice_number = 'AP-INV-20250110-001';
    
    -- Add invoice items
    INSERT INTO ap_invoice_items (id, invoice_id, description, quantity, unit_price, tax_rate, tax_amount, total_amount, account_id)
    VALUES 
    (
        gen_random_uuid(),
        inv_id,
        'Paper supplies',
        50,
        50.00,
        15.00,
        375.00,
        2875.00,
        (SELECT id FROM accounts WHERE code = '6400') -- Office Supplies
    ),
    (
        gen_random_uuid(),
        inv_id,
        'Office stationery',
        10,
        200.00,
        15.00,
        300.00,
        2300.00,
        (SELECT id FROM accounts WHERE code = '6400') -- Office Supplies
    ),
    (
        gen_random_uuid(),
        inv_id,
        'Printer toner',
        1,
        500.00,
        15.00,
        75.00,
        575.00,
        (SELECT id FROM accounts WHERE code = '6400') -- Office Supplies
    );
    
    -- Create journal entry for the invoice
    INSERT INTO journal_entries (id, entry_number, entry_date, description, reference, status, is_recurring, created_by, created_at)
    VALUES (
        gen_random_uuid(),
        'JE-20250110-AP001',
        '2025-01-10',
        'Office supplies invoice',
        'AP-INV-20250110-001',
        'POSTED',
        false,
        'admin',
        CURRENT_TIMESTAMP
    );
    
    -- Get the journal entry ID
    DECLARE
        je_id UUID;
    BEGIN
        SELECT id INTO je_id FROM journal_entries WHERE entry_number = 'JE-20250110-AP001';
        
        -- Update invoice with journal entry ID
        UPDATE ap_invoices SET journal_entry_id = je_id WHERE id = inv_id;
        
        -- Add journal entry lines
        INSERT INTO journal_entry_lines (id, journal_entry_id, account_id, description, debit_amount, credit_amount)
        VALUES 
        (
            gen_random_uuid(),
            je_id,
            (SELECT id FROM accounts WHERE code = '6400'), -- Office Supplies
            'Office supplies purchase',
            5000.00,
            0.00
        ),
        (
            gen_random_uuid(),
            je_id,
            (SELECT id FROM accounts WHERE code = '2300'), -- Taxes Payable
            'VAT on office supplies',
            750.00,
            0.00
        ),
        (
            gen_random_uuid(),
            je_id,
            (SELECT id FROM accounts WHERE code = '2100'), -- Accounts Payable
            'Office supplies invoice',
            0.00,
            5750.00
        );
    END;
    
    -- Create payment for the invoice
    INSERT INTO ap_payments (id, payment_number, vendor_id, payment_date, amount, payment_method, 
                            reference, description, status, currency_code, bank_account_id, 
                            created_by, created_at)
    VALUES (
        gen_random_uuid(),
        'AP-PAY-20250125-001',
        (SELECT id FROM vendors WHERE code = 'V001'),
        '2025-01-25',
        5750.00,
        'BANK_TRANSFER',
        'TRF-001',
        'Payment for office supplies',
        'PROCESSED',
        'SAR',
        (SELECT id FROM accounts WHERE code = '1101'), -- Main Operating Account
        'admin',
        CURRENT_TIMESTAMP
    );
    
    -- Get the payment ID
    DECLARE
        pay_id UUID;
    BEGIN
        SELECT id INTO pay_id FROM ap_payments WHERE payment_number = 'AP-PAY-20250125-001';
        
        -- Add payment allocation
        INSERT INTO ap_invoice_payments (id, payment_id, invoice_id, amount_applied, created_at)
        VALUES (
            gen_random_uuid(),
            pay_id,
            inv_id,
            5750.00,
            CURRENT_TIMESTAMP
        );
        
        -- Create journal entry for the payment
        INSERT INTO journal_entries (id, entry_number, entry_date, description, reference, status, is_recurring, created_by, created_at)
        VALUES (
            gen_random_uuid(),
            'JE-20250125-AP001',
            '2025-01-25',
            'Payment for office supplies',
            'AP-PAY-20250125-001',
            'POSTED',
            false,
            'admin',
            CURRENT_TIMESTAMP
        );
        
        -- Get the journal entry ID
        DECLARE
            je_pay_id UUID;
        BEGIN
            SELECT id INTO je_pay_id FROM journal_entries WHERE entry_number = 'JE-20250125-AP001';
            
            -- Update payment with journal entry ID
            UPDATE ap_payments SET journal_entry_id = je_pay_id WHERE id = pay_id;
            
            -- Add journal entry lines
            INSERT INTO journal_entry_lines (id, journal_entry_id, account_id, description, debit_amount, credit_amount)
            VALUES 
            (
                gen_random_uuid(),
                je_pay_id,
                (SELECT id FROM accounts WHERE code = '2100'), -- Accounts Payable
                'Payment for office supplies',
                5750.00,
                0.00
            ),
            (
                gen_random_uuid(),
                je_pay_id,
                (SELECT id FROM accounts WHERE code = '1101'), -- Main Operating Account
                'Payment for office supplies',
                0.00,
                5750.00
            );
        END;
    END;
END;
$$;

-- Tech Services Invoice (Unpaid)
INSERT INTO ap_invoices (id, invoice_number, vendor_id, vendor_invoice_number, issue_date, due_date, 
                         description, subtotal, tax_amount, total_amount, paid_amount, status, currency_code, 
                         created_by, created_at)
VALUES (
    gen_random_uuid(),
    'AP-INV-20250215-001',
    (SELECT id FROM vendors WHERE code = 'V002'),
    'TS-78901',
    '2025-02-15',
    '2025-03-17',
    'IT services and software',
    20000.00,
    3000.00,
    23000.00,
    0.00,  -- Unpaid
    'APPROVED',
    'SAR',
    'admin',
    CURRENT_TIMESTAMP
);

-- Get the invoice ID
DO $$
DECLARE
    inv_id UUID;
BEGIN
    SELECT id INTO inv_id FROM ap_invoices WHERE invoice_number = 'AP-INV-20250215-001';
    
    -- Add invoice items
    INSERT INTO ap_invoice_items (id, invoice_id, description, quantity, unit_price, tax_rate, tax_amount, total_amount, account_id)
    VALUES 
    (
        gen_random_uuid(),
        inv_id,
        'IT support services - Feb 2025',
        1,
        15000.00,
        15.00,
        2250.00,
        17250.00,
        (SELECT id FROM accounts WHERE code = '6300') -- Utilities Expense (for IT services)
    ),
    (
        gen_random_uuid(),
        inv_id,
        'Software licenses',
        5,
        1000.00,
        15.00,
        750.00,
        5750.00,
        (SELECT id FROM accounts WHERE code = '6300') -- Utilities Expense (for software)
    );
    
    -- Create journal entry for the invoice
    INSERT INTO journal_entries (id, entry_number, entry_date, description, reference, status, is_recurring, created_by, created_at)
    VALUES (
        gen_random_uuid(),
        'JE-20250215-AP001',
        '2025-02-15',
        'IT services and software',
        'AP-INV-20250215-001',
        'POSTED',
        false,
        'admin',
        CURRENT_TIMESTAMP
    );
    
    -- Get the journal entry ID
    DECLARE
        je_id UUID;
    BEGIN
        SELECT id INTO je_id FROM journal_entries WHERE entry_number = 'JE-20250215-AP001';
        
        -- Update invoice with journal entry ID
        UPDATE ap_invoices SET journal_entry_id = je_id WHERE id = inv_id;
        
        -- Add journal entry lines
        INSERT INTO journal_entry_lines (id, journal_entry_id, account_id, description, debit_amount, credit_amount)
        VALUES 
        (
            gen_random_uuid(),
            je_id,
            (SELECT id FROM accounts WHERE code = '6300'), -- Utilities Expense
            'IT services and software',
            20000.00,
            0.00
        ),
        (
            gen_random_uuid(),
            je_id,
            (SELECT id FROM accounts WHERE code = '2300'), -- Taxes Payable
            'VAT on IT services',
            3000.00,
            0.00
        ),
        (
            gen_random_uuid(),
            je_id,
            (SELECT id FROM accounts WHERE code = '2100'), -- Accounts Payable
            'IT services invoice',
            0.00,
            23000.00
        );
    END;
END;
$$;

-- 6. Create AR Invoices

-- Sales Invoice 1 (Paid)
INSERT INTO ar_invoices (id, invoice_number, customer_id, issue_date, due_date, 
                         description, subtotal, tax_amount, total_amount, paid_amount, status, currency_code, 
                         created_by, created_at)
VALUES (
    gen_random_uuid(),
    'AR-INV-20250120-001',
    (SELECT id FROM customers WHERE code = 'C001'),
    '2025-01-20',
    '2025-02-19',
    'Product sales - January 2025',
    50000.00,
    7500.00,
    57500.00,
    57500.00,  -- Fully paid
    'PAID',
    'SAR',
    'admin',
    CURRENT_TIMESTAMP
);

-- Get the invoice ID
DO $$
DECLARE
    inv_id UUID;
BEGIN
    SELECT id INTO inv_id FROM ar_invoices WHERE invoice_number = 'AR-INV-20250120-001';
    
    -- Add invoice items
    INSERT INTO ar_invoice_items (id, invoice_id, description, quantity, unit_price, tax_rate, tax_amount, total_amount, account_id)
    VALUES 
    (
        gen_random_uuid(),
        inv_id,
        'Product A',
        20,
        1500.00,
        15.00,
        4500.00,
        34500.00,
        (SELECT id FROM accounts WHERE code = '4100') -- Sales Revenue
    ),
    (
        gen_random_uuid(),
        inv_id,
        'Product B',
        10,
        2000.00,
        15.00,
        3000.00,
        23000.00,
        (SELECT id FROM accounts WHERE code = '4100') -- Sales Revenue
    );
    
    -- Create journal entry for the invoice
    INSERT INTO journal_entries (id, entry_number, entry_date, description, reference, status, is_recurring, created_by, created_at)
    VALUES (
        gen_random_uuid(),
        'JE-20250120-AR001',
        '2025-01-20',
        'Product sales - January 2025',
        'AR-INV-20250120-001',
        'POSTED',
        false,
        'admin',
        CURRENT_TIMESTAMP
    );
    
    -- Get the journal entry ID
    DECLARE
        je_id UUID;
    BEGIN
        SELECT id INTO je_id FROM journal_entries WHERE entry_number = 'JE-20250120-AR001';
        
        -- Update invoice with journal entry ID
        UPDATE ar_invoices SET journal_entry_id = je_id WHERE id = inv_id;
        
        -- Add journal entry lines
        INSERT INTO journal_entry_lines (id, journal_entry_id, account_id, description, debit_amount, credit_amount)
        VALUES 
        (
            gen_random_uuid(),
            je_id,
            (SELECT id FROM accounts WHERE code = '1200'), -- Accounts Receivable
            'Product sales invoice',
            57500.00,
            0.00
        ),
        (
            gen_random_uuid(),
            je_id,
            (SELECT id FROM accounts WHERE code = '4100'), -- Sales Revenue
            'Product sales',
            0.00,
            50000.00
        ),
        (
            gen_random_uuid(),
            je_id,
            (SELECT id FROM accounts WHERE code = '2300'), -- Taxes Payable
            'VAT on sales',
            0.00,
            7500.00
        );
    END;
    
    -- Create payment for the invoice
    INSERT INTO ar_payments (id, payment_number, customer_id, payment_date, amount, payment_method, 
                            reference, description, status, currency_code, bank_account_id, 
                            created_by, created_at)
    VALUES (
        gen_random_uuid(),
        'AR-PAY-20250205-001',
        (SELECT id FROM customers WHERE code = 'C001'),
        '2025-02-05',
        57500.00,
        'BANK_TRANSFER',
        'TRF-002',
        'Payment for January sales',
        'PROCESSED',
        'SAR',
        (SELECT id FROM accounts WHERE code = '1101'), -- Main Operating Account
        'admin',
        CURRENT_TIMESTAMP
    );
    
    -- Get the payment ID
    DECLARE
        pay_id UUID;
    BEGIN
        SELECT id INTO pay_id FROM ar_payments WHERE payment_number = 'AR-PAY-20250205-001';
        
        -- Add payment allocation
        INSERT INTO ar_invoice_payments (id, payment_id, invoice_id, amount_applied, created_at)
        VALUES (
            gen_random_uuid(),
            pay_id,
            inv_id,
            57500.00,
            CURRENT_TIMESTAMP
        );
        
        -- Create journal entry for the payment
        INSERT INTO journal_entries (id, entry_number, entry_date, description, reference, status, is_recurring, created_by, created_at)
        VALUES (
            gen_random_uuid(),
            'JE-20250205-AR001',
            '2025-02-05',
            'Payment received for January sales',
            'AR-PAY-20250205-001',
            'POSTED',
            false,
            'admin',
            CURRENT_TIMESTAMP
        );
        
        -- Get the journal entry ID
        DECLARE
            je_pay_id UUID;
        BEGIN
            SELECT id INTO je_pay_id FROM journal_entries WHERE entry_number = 'JE-20250205-AR001';
            
            -- Update payment with journal entry ID
            UPDATE ar_payments SET journal_entry_id = je_pay_id WHERE id = pay_id;
            
            -- Add journal entry lines
            INSERT INTO journal_entry_lines (id, journal_entry_id, account_id, description, debit_amount, credit_amount)
            VALUES 
            (
                gen_random_uuid(),
                je_pay_id,
                (SELECT id FROM accounts WHERE code = '1101'), -- Main Operating Account
                'Payment received for January sales',
                57500.00,
                0.00
            ),
            (
                gen_random_uuid(),
                je_pay_id,
                (SELECT id FROM accounts WHERE code = '1200'), -- Accounts Receivable
                'Payment received for January sales',
                0.00,
                57500.00
            );
        END;
    END;
END;
$$;

-- Sales Invoice 2 (Partially Paid)
INSERT INTO ar_invoices (id, invoice_number, customer_id, issue_date, due_date, 
                         description, subtotal, tax_amount, total_amount, paid_amount, status, currency_code, 
                         created_by, created_at)
VALUES (
    gen_random_uuid(),
    'AR-INV-20250210-001',
    (SELECT id FROM customers WHERE code = 'C002'),
    '2025-02-10',
    '2025-03-12',
    'Services rendered - February 2025',
    100000.00,
    15000.00,
    115000.00,
    50000.00,  -- Partially paid
    'PARTIALLY_PAID',
    'SAR',
    'admin',
    CURRENT_TIMESTAMP
);

-- Continuing the test data script for the partially paid invoice

DO $$
DECLARE
    inv_id UUID;
BEGIN
    SELECT id INTO inv_id FROM ar_invoices WHERE invoice_number = 'AR-INV-20250210-001';
    
    -- Create journal entry for the invoice
    INSERT INTO journal_entries (id, entry_number, entry_date, description, reference, status, is_recurring, created_by, created_at)
    VALUES (
        gen_random_uuid(),
        'JE-20250210-AR001',
        '2025-02-10',
        'Services rendered - February 2025',
        'AR-INV-20250210-001',
        'POSTED',
        false,
        'admin',
        CURRENT_TIMESTAMP
    );
    
    -- Get the journal entry ID
    DECLARE
        je_id UUID;
    BEGIN
        SELECT id INTO je_id FROM journal_entries WHERE entry_number = 'JE-20250210-AR001';
        
        -- Update invoice with journal entry ID
        UPDATE ar_invoices SET journal_entry_id = je_id WHERE id = inv_id;
        
        -- Add journal entry lines
        INSERT INTO journal_entry_lines (id, journal_entry_id, account_id, description, debit_amount, credit_amount)
        VALUES 
        (
            gen_random_uuid(),
            je_id,
            (SELECT id FROM accounts WHERE code = '1200'), -- Accounts Receivable
            'Service revenue invoice',
            115000.00,
            0.00
        ),
        (
            gen_random_uuid(),
            je_id,
            (SELECT id FROM accounts WHERE code = '4200'), -- Service Revenue
            'Service revenue',
            0.00,
            100000.00
        ),
        (
            gen_random_uuid(),
            je_id,
            (SELECT id FROM accounts WHERE code = '2300'), -- Taxes Payable
            'VAT on services',
            0.00,
            15000.00
        );
    END;
    
    -- Create partial payment for the invoice
    INSERT INTO ar_payments (id, payment_number, customer_id, payment_date, amount, payment_method, 
                            reference, description, status, currency_code, bank_account_id, 
                            created_by, created_at)
    VALUES (
        gen_random_uuid(),
        'AR-PAY-20250225-001',
        (SELECT id FROM customers WHERE code = 'C002'),
        '2025-02-25',
        50000.00,
        'BANK_TRANSFER',
        'TRF-003',
        'Partial payment for February services',
        'PROCESSED',
        'SAR',
        (SELECT id FROM accounts WHERE code = '1101'), -- Main Operating Account
        'admin',
        CURRENT_TIMESTAMP
    );
    
    -- Get the payment ID
    DECLARE
        pay_id UUID;
    BEGIN
        SELECT id INTO pay_id FROM ar_payments WHERE payment_number = 'AR-PAY-20250225-001';
        
        -- Add payment allocation
        INSERT INTO ar_invoice_payments (id, payment_id, invoice_id, amount_applied, created_at)
        VALUES (
            gen_random_uuid(),
            pay_id,
            inv_id,
            50000.00,
            CURRENT_TIMESTAMP
        );
        
        -- Create journal entry for the payment
        INSERT INTO journal_entries (id, entry_number, entry_date, description, reference, status, is_recurring, created_by, created_at)
        VALUES (
            gen_random_uuid(),
            'JE-20250225-AR001',
            '2025-02-25',
            'Partial payment received for February services',
            'AR-PAY-20250225-001',
            'POSTED',
            false,
            'admin',
            CURRENT_TIMESTAMP
        );
        
        -- Get the journal entry ID
        DECLARE
            je_pay_id UUID;
        BEGIN
            SELECT id INTO je_pay_id FROM journal_entries WHERE entry_number = 'JE-20250225-AR001';
            
            -- Update payment with journal entry ID
            UPDATE ar_payments SET journal_entry_id = je_pay_id WHERE id = pay_id;
            
            -- Add journal entry lines
            INSERT INTO journal_entry_lines (id, journal_entry_id, account_id, description, debit_amount, credit_amount)
            VALUES 
            (
                gen_random_uuid(),
                je_pay_id,
                (SELECT id FROM accounts WHERE code = '1101'), -- Main Operating Account
                'Partial payment received for February services',
                50000.00,
                0.00
            ),
            (
                gen_random_uuid(),
                je_pay_id,
                (SELECT id FROM accounts WHERE code = '1200'), -- Accounts Receivable
                'Partial payment received for February services',
                0.00,
                50000.00
            );
        END;
    END;
END;
$$;

-- 7. Record Monthly Salary Expense
INSERT INTO journal_entries (id, entry_number, entry_date, description, reference, status, is_recurring, created_by, created_at)
VALUES (
    gen_random_uuid(),
    'JE-20250131-SAL',
    '2025-01-31',
    'January 2025 salaries',
    'SAL-JAN2025',
    'POSTED',
    false,
    'admin',
    CURRENT_TIMESTAMP
);

-- Get the journal entry ID
DO $$
DECLARE
    je_id UUID;
BEGIN
    SELECT id INTO je_id FROM journal_entries WHERE entry_number = 'JE-20250131-SAL';
    
    -- Add journal entry lines
    INSERT INTO journal_entry_lines (id, journal_entry_id, account_id, description, debit_amount, credit_amount)
    VALUES 
    (
        gen_random_uuid(),
        je_id,
        (SELECT id FROM accounts WHERE code = '6100'), -- Salaries Expense
        'January 2025 salaries',
        40000.00,
        0.00
    ),
    (
        gen_random_uuid(),
        je_id,
        (SELECT id FROM accounts WHERE code = '1101'), -- Main Operating Account
        'Payment of January 2025 salaries',
        0.00,
        40000.00
    );
END;
$$;

-- February Salary Expense
INSERT INTO journal_entries (id, entry_number, entry_date, description, reference, status, is_recurring, created_by, created_at)
VALUES (
    gen_random_uuid(),
    'JE-20250228-SAL',
    '2025-02-28',
    'February 2025 salaries',
    'SAL-FEB2025',
    'POSTED',
    false,
    'admin',
    CURRENT_TIMESTAMP
);

-- Get the journal entry ID
DO $$
DECLARE
    je_id UUID;
BEGIN
    SELECT id INTO je_id FROM journal_entries WHERE entry_number = 'JE-20250228-SAL';
    
    -- Add journal entry lines
    INSERT INTO journal_entry_lines (id, journal_entry_id, account_id, description, debit_amount, credit_amount)
    VALUES 
    (
        gen_random_uuid(),
        je_id,
        (SELECT id FROM accounts WHERE code = '6100'), -- Salaries Expense
        'February 2025 salaries',
        40000.00,
        0.00
    ),
    (
        gen_random_uuid(),
        je_id,
        (SELECT id FROM accounts WHERE code = '1101'), -- Main Operating Account
        'Payment of February 2025 salaries',
        0.00,
        40000.00
    );
END;
$$;

-- 8. Record Rent Expense
INSERT INTO journal_entries (id, entry_number, entry_date, description, reference, status, is_recurring, created_by, created_at)
VALUES (
    gen_random_uuid(),
    'JE-20250131-RENT',
    '2025-01-31',
    'Office rent - January 2025',
    'RENT-JAN2025',
    'POSTED',
    false,
    'admin',
    CURRENT_TIMESTAMP
);

-- Get the journal entry ID
DO $$
DECLARE
    je_id UUID;
BEGIN
    SELECT id INTO je_id FROM journal_entries WHERE entry_number = 'JE-20250131-RENT';
    
    -- Add journal entry lines
    INSERT INTO journal_entry_lines (id, journal_entry_id, account_id, description, debit_amount, credit_amount)
    VALUES 
    (
        gen_random_uuid(),
        je_id,
        (SELECT id FROM accounts WHERE code = '6200'), -- Rent Expense
        'Office rent - January 2025',
        15000.00,
        0.00
    ),
    (
        gen_random_uuid(),
        je_id,
        (SELECT id FROM accounts WHERE code = '1101'), -- Main Operating Account
        'Payment of January 2025 office rent',
        0.00,
        15000.00
    );
END;
$$;

-- February Rent Expense
INSERT INTO journal_entries (id, entry_number, entry_date, description, reference, status, is_recurring, created_by, created_at)
VALUES (
    gen_random_uuid(),
    'JE-20250228-RENT',
    '2025-02-28',
    'Office rent - February 2025',
    'RENT-FEB2025',
    'POSTED',
    false,
    'admin',
    CURRENT_TIMESTAMP
);

-- Get the journal entry ID
DO $$
DECLARE
    je_id UUID;
BEGIN
    SELECT id INTO je_id FROM journal_entries WHERE entry_number = 'JE-20250228-RENT';
    
    -- Add journal entry lines
    INSERT INTO journal_entry_lines (id, journal_entry_id, account_id, description, debit_amount, credit_amount)
    VALUES 
    (
        gen_random_uuid(),
        je_id,
        (SELECT id FROM accounts WHERE code = '6200'), -- Rent Expense
        'Office rent - February 2025',
        15000.00,
        0.00
    ),
    (
        gen_random_uuid(),
        je_id,
        (SELECT id FROM accounts WHERE code = '1101'), -- Main Operating Account
        'Payment of February 2025 office rent',
        0.00,
        15000.00
    );
END;
$$;

-- 9. Record Monthly Depreciation
INSERT INTO journal_entries (id, entry_number, entry_date, description, reference, status, is_recurring, created_by, created_at)
VALUES (
    gen_random_uuid(),
    'JE-20250131-DEP',
    '2025-01-31',
    'Depreciation expense - January 2025',
    'DEP-JAN2025',
    'POSTED',
    false,
    'admin',
    CURRENT_TIMESTAMP
);

-- Get the journal entry ID
DO $$
DECLARE
    je_id UUID;
BEGIN
    SELECT id INTO je_id FROM journal_entries WHERE entry_number = 'JE-20250131-DEP';
    
    -- Add journal entry lines
    INSERT INTO journal_entry_lines (id, journal_entry_id, account_id, description, debit_amount, credit_amount)
    VALUES 
    (
        gen_random_uuid(),
        je_id,
        (SELECT id FROM accounts WHERE code = '6700'), -- Depreciation Expense
        'Depreciation expense - January 2025',
        2000.00,
        0.00
    ),
    (
        gen_random_uuid(),
        je_id,
        (SELECT id FROM accounts WHERE code = '1610'), -- Accumulated Depreciation - Equipment
        'Accumulated depreciation',
        0.00,
        2000.00
    );
END;
$$;

-- February Depreciation Expense
INSERT INTO journal_entries (id, entry_number, entry_date, description, reference, status, is_recurring, created_by, created_at)
VALUES (
    gen_random_uuid(),
    'JE-20250228-DEP',
    '2025-02-28',
    'Depreciation expense - February 2025',
    'DEP-FEB2025',
    'POSTED',
    false,
    'admin',
    CURRENT_TIMESTAMP
);

-- Get the journal entry ID
DO $$
DECLARE
    je_id UUID;
BEGIN
    SELECT id INTO je_id FROM journal_entries WHERE entry_number = 'JE-20250228-DEP';
    
    -- Add journal entry lines
    INSERT INTO journal_entry_lines (id, journal_entry_id, account_id, description, debit_amount, credit_amount)
    VALUES 
    (
        gen_random_uuid(),
        je_id,
        (SELECT id FROM accounts WHERE code = '6700'), -- Depreciation Expense
        'Depreciation expense - February 2025',
        2000.00,
        0.00
    ),
    (
        gen_random_uuid(),
        je_id,
        (SELECT id FROM accounts WHERE code = '1610'), -- Accumulated Depreciation - Equipment
        'Accumulated depreciation',
        0.00,
        2000.00
    );
END;
$$;

-- Record some interest income 
INSERT INTO journal_entries (id, entry_number, entry_date, description, reference, status, is_recurring, created_by, created_at)
VALUES (
    gen_random_uuid(),
    'JE-20250228-INT',
    '2025-02-28',
    'Interest income - February 2025',
    'INT-FEB2025',
    'POSTED',
    false,
    'admin',
    CURRENT_TIMESTAMP
);

-- Get the journal entry ID
DO $$
DECLARE
    je_id UUID;
BEGIN
    SELECT id INTO je_id FROM journal_entries WHERE entry_number = 'JE-20250228-INT';
    
    -- Add journal entry lines
    INSERT INTO journal_entry_lines (id, journal_entry_id, account_id, description, debit_amount, credit_amount)
    VALUES 
    (
        gen_random_uuid(),
        je_id,
        (SELECT id FROM accounts WHERE code = '1101'), -- Main Operating Account
        'Interest income received',
        1500.00,
        0.00
    ),
    (
        gen_random_uuid(),
        je_id,
        (SELECT id FROM accounts WHERE code = '4300'), -- Interest Income
        'Interest income - February 2025',
        0.00,
        1500.00
    );
END;
$$;

-- 10. Add Some VAT Payment to Government
INSERT INTO journal_entries (id, entry_number, entry_date, description, reference, status, is_recurring, created_by, created_at)
VALUES (
    gen_random_uuid(),
    'JE-20250215-VAT',
    '2025-02-15',
    'VAT payment to government - Q4 2024',
    'VAT-Q42024',
    'POSTED',
    false,
    'admin',
    CURRENT_TIMESTAMP
);

-- Get the journal entry ID
DO $$
DECLARE
    je_id UUID;
BEGIN
    SELECT id INTO je_id FROM journal_entries WHERE entry_number = 'JE-20250215-VAT';
    
    -- Add journal entry lines
    INSERT INTO journal_entry_lines (id, journal_entry_id, account_id, description, debit_amount, credit_amount)
    VALUES 
    (
        gen_random_uuid(),
        je_id,
        (SELECT id FROM accounts WHERE code = '2300'), -- Taxes Payable
        'VAT payment to government - Q4 2024',
        10000.00,
        0.00
    ),
    (
        gen_random_uuid(),
        je_id,
        (SELECT id FROM accounts WHERE code = '1101'), -- Main Operating Account
        'VAT payment to government - Q4 2024',
        0.00,
        10000.00
    );
END;
$$;