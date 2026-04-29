from flask import Blueprint, render_template

menu_bp = Blueprint("menu", __name__)

# Dummy data dictionary structured for easy future API transition
DUMMY_DATA = {
    "categories": [
        {"id": "c1", "name": "Hot Beverages", "image": "https://placehold.co/300x200/e1f5fe/0288d1?text=Coffee"},
        {"id": "c2", "name": "Main Courses", "image": "https://placehold.co/300x200/e1f5fe/0288d1?text=Meals"},
        {"id": "c3", "name": "Desserts", "image": "https://placehold.co/300x200/e1f5fe/0288d1?text=Desserts"}
    ],
    "products": {
        "c1": [
            {"id": "p1", "name": "Latte", "price": "$4.50", "description": "Freshly brewed espresso with steamed milk.", "image": "https://placehold.co/300x200/e1f5fe/0288d1?text=Latte"},
            {"id": "p2", "name": "Green Tea", "price": "$3.00", "description": "Organic soothing green tea.", "image": "https://placehold.co/300x200/e1f5fe/0288d1?text=Green+Tea"}
        ],
        "c2": [
            {"id": "p3", "name": "Classic Burger", "price": "$12.00", "description": "Beef patty, cheddar, lettuce, and our secret sauce.", "image": "https://placehold.co/300x200/e1f5fe/0288d1?text=Burger"},
            {"id": "p4", "name": "Margherita Pizza", "price": "$14.00", "description": "Tomato sauce, fresh mozzarella, and basil.", "image": "https://placehold.co/300x200/e1f5fe/0288d1?text=Pizza"}
        ],
        "c3": [
            {"id": "p5", "name": "Cheesecake", "price": "$6.00", "description": "New York style cheesecake with berry compote.", "image": "https://placehold.co/300x200/e1f5fe/0288d1?text=Cheesecake"}
        ]
    }
}

@menu_bp.route("/")
def get_menu():
    return render_template('index.html', data=DUMMY_DATA)