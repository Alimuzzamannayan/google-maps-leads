"""
Test file for email reporting
"""
import reporter

# Create fake stats
stats = {
    'total_leads': 150,
    'new_companies': ["Maldives Cafe", "Ocean Resort", "Blue Lagoon Pharmacy"],
    'updated_companies': ["Male Hospital"],
    'category_breakdown': {"Cafe": 12, "Resort": 8, "Clinic": 5},
    'locations_breakdown': {"Male": 80, "Hulhumale": 40, "Addu": 30},
    'companies_with_phone': 90,
    'companies_with_email': 45,
    'companies_with_website': 60,
    'new_companies_details': [
        {'name': 'Maldives Cafe', 'category': 'Cafe', 'country': 'Male', 'phone': '+960 1234', 'email': 'cafe@test.com', 'website': 'http://cafe.com'},
        {'name': 'Ocean Resort', 'category': 'Resort', 'country': 'Hulhumale', 'phone': '+960 5678', 'email': 'resort@test.com', 'website': 'http://resort.com'},
        {'name': 'Blue Lagoon Pharmacy', 'category': 'Pharmacy', 'country': 'Addu', 'phone': '+960 9012', 'email': 'pharmacy@test.com', 'website': 'http://pharmacy.com'},
    ],
    'updated_companies_details': [
        {'name': 'Male Hospital', 'category': 'Hospital', 'country': 'Male', 'phone': '+960 1111', 'email': 'hospital@test.com', 'website': 'http://hospital.com'},
    ]
}

# Create fake errors
errors = ["Connection timeout on query 3"]

# Send the report
reporter.send_report(stats, errors)

print("Test complete")
