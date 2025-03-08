from django.contrib.auth.models import User
from trading.models import Profile

# Create multiple users and their profiles with an initial balance
users = []
for i in range(1, 11):  # Create users user1 to user10
    user = User.objects.create_user(username=f"user{i}", password="password1234")
    users.append(user)
    # Create a profile for each user
    Profile.objects.create(user=user, balance=1500)

print(f"{len(users)} Users and their Profiles created successfully!")