import random
from faker import Faker
from locust import HttpUser, task, TaskSet, SequentialTaskSet, constant_throughput

fake = Faker('ru_RU')

TEST_USER = {
    "email": "loadtest_buyer@example.com",
    "password": "TestPassword123",
}

TEST_MERCH = {
    "email": "loadtest_merch@example.com",
    "password": "TestPassword123",
}


class BuyerBehavior(TaskSet):
    def on_start(self):
        self.client.post(
            "/api/auth/login/",
            json={"email": TEST_USER["email"], "password": TEST_USER["password"]},
            name="/api/auth/login/",
        )
        
        self.authenticated = True

        self.all_book_ids = []
        with self.client.get("/api/books/", catch_response=True, name="/api/books/ (warmup)") as resp:
            if resp.status_code == 200:
                data = resp.json()
                self.all_book_ids = [b["id"] for b in data.get("results", [])][:20]
        if not self.all_book_ids:
            self.all_book_ids = [1]
            
        self.available_book_ids = list(self.all_book_ids)

    @task(10)
    def browse_books(self):
        page = random.randint(1, 3)
        self.client.get(f"/api/books/?page={page}", name="/api/books/?page=[N]")

    @task(10)
    def book_detail(self):
        if not getattr(self, "authenticated", False):
            return
        book_id = random.choice(self.all_book_ids)
        self.client.get(f"/api/books/{book_id}/", name="/api/books/[id]/")

    @task(10)
    def get_cart(self):
        if not getattr(self, "authenticated", False):
            return
        self.client.get("/api/cart/", name="/api/cart/")

    @task(1)
    def add_to_cart(self):
        if not getattr(self, "authenticated", False):
            return

        self.client.delete("/api/cart/clear/", name="/api/cart/clear/")

        book_id = random.choice(self.all_book_ids)

        with self.client.post(
            "/api/cart/add/",
            json={"book_id": book_id},
            catch_response=True,
            name="/api/cart/add/",
        ) as resp:
            if resp.status_code != 200:
                print(f"\n!!! ОШИБКА 400 !!! Ответ сервера: {resp.text}\n")
                resp.failure(f"400: {resp.text}")

    @task(1)
    def create_review(self):
        if not getattr(self, "authenticated", False):
            return
        book_id = random.choice(self.all_book_ids)
        payload = {
            "rating": random.randint(1, 5),
            "comment": fake.paragraph(nb_sentences=2),
        }
        self.client.post(
            f"/api/books/{book_id}/reviews/create/",
            json=payload,
            name="/api/books/[id]/reviews/create/",
        )


class MerchandiserBehavior(SequentialTaskSet):
    def on_start(self):
        self.client.post(
            "/api/auth/login/",
            json={"email": TEST_MERCH["email"], "password": TEST_MERCH["password"]},
            name="/api/auth/login/ (merch)",
        )
        self.authenticated = True

    @task
    def view_carts(self):
        if not getattr(self, "authenticated", False):
            return
        self.client.get("/api/merchandiser/carts/?page=1", name="/api/merchandiser/carts/")

    @task
    def mark_all_read(self):
        if not getattr(self, "authenticated", False):
            return
        self.client.post(
            "/api/notifications/read-all/",
            json={},
            name="/api/notifications/read-all/",
        )


class BuyerUser(HttpUser):
    wait_time = constant_throughput(3)
    tasks = [BuyerBehavior]
    weight = 4


class MerchUser(HttpUser):
    wait_time = constant_throughput(2)
    tasks = [MerchandiserBehavior]
    weight = 1