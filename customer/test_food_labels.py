from django.template import Context, Template
from django.test import SimpleTestCase
from django.utils.translation import override

from .templatetags.food_labels import food_label, food_name_translations


class FoodLabelTests(SimpleTestCase):
    def test_names_follow_selected_language(self):
        with override("ru"):
            self.assertEqual(food_label("Chicken Caesar Salad"), "Салат Цезарь с курицей")
            self.assertEqual(food_label("French Fries"), "Картофель фри")
            self.assertEqual(food_label("Margherita Pizza"), "Пицца Маргарита")
            self.assertEqual(food_label("Restaurant special"), "Restaurant special")
        with override("en"):
            self.assertEqual(food_label("Chicken Caesar Salad"), "Chicken Caesar Salad")

    def test_existing_favorites_follow_selected_language(self):
        with override("ru"):
            names = food_name_translations()
            self.assertEqual(names["Cheeseburger"], "Чизбургер")
        with override("en"):
            names = food_name_translations()
            self.assertEqual(names["Чизбургер"], "Cheeseburger")
            self.assertEqual(names["Пицца Маргарита"], "Margherita Pizza")

    def test_template_escapes_custom_dish_names(self):
        template = Template("{% load food_labels %}{{ name|food_label }}")
        with override("ru"):
            self.assertEqual(template.render(Context({"name": "Cola"})), "Кола")
            self.assertEqual(template.render(Context({"name": "<test>"})), "&lt;test&gt;")
