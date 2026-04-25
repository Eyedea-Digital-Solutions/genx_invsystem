import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from inventory.models import Joint, Product, Stock, StockMovement, StockTake


class StockTakeSubmitTests(TestCase):
    def setUp(self):
        self.user_model = get_user_model()
        self.user = self.user_model.objects.create_user(
            username='manager',
            password='pass1234',
            role=self.user_model.ROLE_MANAGER,
        )
        self.client.force_login(self.user)

        self.joint = Joint.objects.create(name='genx', display_name='GenX')
        self.product = Product.objects.create(
            joint=self.joint,
            name='Runner',
            code='RUN-1',
            price='25.00',
        )
        self.stock = Stock.objects.create(product=self.product, quantity=4, min_quantity=1)

    def test_stock_take_submit_creates_records_and_updates_stock(self):
        response = self.client.post(
            reverse('inventory:api_stock_take_submit'),
            data=json.dumps({
                'joint_id': self.joint.pk,
                'notes': 'Final sign off',
                'setup_notes': 'Cycle count',
                'counts': [{'product_id': self.product.pk, 'counted_qty': 6}],
            }),
            content_type='application/json',
            secure=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['ok'])

        take = StockTake.objects.get(joint=self.joint)
        item = take.items.get(product=self.product)
        movement = StockMovement.objects.get(product=self.product)

        self.stock.refresh_from_db()

        self.assertEqual(take.notes, 'Cycle count\n\nFinal sign off')
        self.assertEqual(item.system_count, 4)
        self.assertEqual(item.actual_count, 6)
        self.assertEqual(item.variance, 2)
        self.assertEqual(self.stock.quantity, 6)
        self.assertEqual(movement.movement_type, StockMovement.TYPE_STOCK_TAKE)
        self.assertEqual(movement.quantity, 2)
        self.assertEqual(movement.stock_before, 4)
        self.assertEqual(movement.stock_after, 6)
