from django.contrib.auth.models import User
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from trading.models import Profile, StockHolding
import finnhub
from django.http import JsonResponse
from .utils import get_stock_price

# Initialize Finnhub client (Use your API key)
finnhub_client = finnhub.Client(api_key="cv48q2pr01qn2ga8psrgcv48q2pr01qn2ga8pss0")

# ✅ User Registration (Manually Adding Users, So Not Needed)
# ✅ Login - JWT Already Handled by TokenObtainPairView

# 🔹 Buy Stock
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def buy_stock(request):
    user = request.user
    profile = Profile.objects.get(user=user)

    stock_symbol = request.data.get("symbol")
    quantity = int(request.data.get("quantity", 0))

    # Fetch stock price
    stock_data = finnhub_client.quote(stock_symbol)
    current_price = stock_data["c"]

    total_cost = current_price * quantity

    # Check if user has enough balance
    if profile.balance < total_cost:
        return Response({"error": "Insufficient funds"}, status=400)

    # Deduct balance and add stock holding
    profile.balance -= total_cost
    profile.save()

    holding, created = StockHolding.objects.get_or_create(user=user, stock_symbol=stock_symbol)
    holding.quantity += quantity
    holding.save()

    return Response({
        "message": "Stock purchased successfully",
        "remaining_balance": profile.balance,
        "stock_holdings": list(StockHolding.objects.filter(user=user).values('stock_symbol', 'quantity'))
    })

# 🔹 Sell Stock
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def sell_stock(request):
    user = request.user
    profile = Profile.objects.get(user=user)

    stock_symbol = request.data.get("symbol")
    quantity = int(request.data.get("quantity", 0))

    stock_data = finnhub_client.quote(stock_symbol)
    current_price = stock_data["c"]

    holding = StockHolding.objects.filter(user=user, stock_symbol=stock_symbol).first()

    if not holding or holding.quantity < quantity:
        return Response({"error": "Not enough stocks to sell"}, status=400)

    # Process sale
    total_earnings = current_price * quantity 
    total_earnings *= (1-0.8/100)
    profile.balance += total_earnings
    profile.save()

    holding.quantity -= quantity
    if holding.quantity == 0:
        holding.delete()
    else:
        holding.save()

    return Response({
        "message": "Stock sold successfully",
        "remaining_balance": profile.balance,
        "stock_holdings": list(StockHolding.objects.filter(user=user).values('stock_symbol', 'quantity'))
    })

# 🔹 Get User's Stock Holdings
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def stock_holdings(request):
    user = request.user

    # Fetch stock holdings
    holdings = StockHolding.objects.filter(user=user).values('stock_symbol', 'quantity')

    # Fetch user balance
    try:
        profile = Profile.objects.get(user=user)
        balance = profile.balance
    except Profile.DoesNotExist:
        balance = 0  # Default balance if profile doesn't exist

    return Response({
        "username": user.username,
        "balance": balance,  # Add balance to response
        "stock_holdings": list(holdings)
    })

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def all_users_holdings(request):
    """
    API for superusers to see all users' stock holdings and balance.
    """
    if not request.user.is_superuser:  # Ensure only superusers can access
        return JsonResponse({"error": "Permission denied"}, status=403)

    users = User.objects.all()
    data = []

    for user in users:
        # Ensure profile exists or create it if missing
        profile, _ = Profile.objects.get_or_create(user=user, defaults={"balance": 0})

        # Fetch stock holdings
        holdings = StockHolding.objects.filter(user=user)

        holdings_data = [
            {
                "stock_symbol": holding.stock_symbol,
                "quantity": holding.quantity,
            }
            for holding in holdings
        ]

        user_data = {
            "username": user.username,
            "balance": profile.balance,  # Ensure balance is included
            "stock_holdings": holdings_data,
        }
        data.append(user_data)

    return JsonResponse({"users": data}, safe=False)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def update_user_balance(request):
    """
    API for superusers to update a user's balance.
    """
    if not request.user.is_superuser:
        return JsonResponse({"error": "Permission denied"}, status=403)

    data = request.data
    username = data.get("username")
    new_balance = data.get("balance")

    try:
        user = User.objects.get(username=username)
        profile = Profile.objects.get(user=user)
        profile.balance = new_balance
        profile.save()

        return JsonResponse({"message": f"Updated {username}'s balance to {new_balance}"})
    except User.DoesNotExist:
        return JsonResponse({"error": "User not found"}, status=404)
    except Profile.DoesNotExist:
        return JsonResponse({"error": "Profile not found"}, status=404)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def net_portfolio_value(request):
    """
    API to calculate the total net value of the user's portfolio,
    including balance and stock holdings at current market price.
    """
    user = request.user
    
    # Get user balance
    profile, _ = Profile.objects.get_or_create(user=user, defaults={"balance": 0})
    balance = profile.balance

    # Get stock holdings
    holdings = StockHolding.objects.filter(user=user)
    total_stock_value = 0

    stock_data = []
    for holding in holdings:
        stock_price = get_stock_price(holding.stock_symbol)  # Get current price from Finnhub
        if stock_price is not None:
            stock_value = holding.quantity * stock_price
            total_stock_value += stock_value
        else:
            stock_value = None  # If price fetch fails, set as None

        stock_data.append({
            "stock_symbol": holding.stock_symbol,
            "quantity": holding.quantity,
            "current_price": stock_price,
            "total_value": stock_value
        })

    # Calculate net portfolio value
    net_value = balance + total_stock_value

    return JsonResponse({
        "username": user.username,
        "balance": balance,
        "total_stock_value": total_stock_value,
        "net_portfolio_value": net_value,
        "stock_holdings": stock_data
    }, safe=False)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def all_users_portfolio_value(request):
    """
    API for superusers to view all users' net portfolio values, sorted in descending order.
    """
    if not request.user.is_superuser:  # Ensure only superusers can access
        return JsonResponse({"error": "Permission denied"}, status=403)

    user_data = []

    # Fetch all users
    users = User.objects.all()

    for user in users:
        profile, _ = Profile.objects.get_or_create(user=user, defaults={"balance": 0})
        balance = profile.balance

        # Fetch stock holdings
        holdings = StockHolding.objects.filter(user=user)
        total_stock_value = 0

        stock_data = []
        for holding in holdings:
            stock_price = get_stock_price(holding.stock_symbol)  # Fetch stock price
            if stock_price is not None:
                stock_value = holding.quantity * stock_price
                total_stock_value += stock_value
            else:
                stock_value = None  # If price fetch fails

            stock_data.append({
                "stock_symbol": holding.stock_symbol,
                "quantity": holding.quantity,
                "current_price": stock_price,
                "total_value": stock_value
            })

        # Calculate net portfolio value
        net_value = balance + total_stock_value

        user_data.append({
            "username": user.username,
            "balance": balance,
            "total_stock_value": total_stock_value,
            "net_portfolio_value": net_value,
            "stock_holdings": stock_data
        })

    # Sort users by net portfolio value in descending order
    sorted_users = sorted(user_data, key=lambda x: x["net_portfolio_value"], reverse=True)

    return JsonResponse({"users": sorted_users}, safe=False)



@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_user(request):
    """
    API for superusers to create a new user with a specific balance.
    """
    if not request.user.is_superuser:  # Ensure only superusers can access
        return JsonResponse({"error": "Permission denied"}, status=403)

    data = request.data
    username = data.get("username")
    password = data.get("password")
    balance = data.get("balance", 0)  # Default balance is 0

    # Validate input
    if not username or not password:
        return JsonResponse({"error": "Username and password are required"}, status=400)

    if User.objects.filter(username=username).exists():
        return JsonResponse({"error": "Username already exists"}, status=400)

    # Create user
    user = User.objects.create_user(username=username, password=password)

    # Create Profile with balance
    profile = Profile.objects.create(user=user, balance=balance)

    return JsonResponse({
        "message": "User created successfully",
        "username": user.username,
        "balance": profile.balance
    })



@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def delete_user(request):
    """
    API for superusers to delete a user completely.
    """
    if not request.user.is_superuser:  # Ensure only superusers can access
        return JsonResponse({"error": "Permission denied"}, status=403)

    data = request.data
    username = data.get("username")

    if not username:
        return JsonResponse({"error": "Username is required"}, status=400)

    try:
        user = User.objects.get(username=username)
        user.delete()  # This will delete the user and cascade delete related profiles
        return JsonResponse({"message": f"User '{username}' deleted successfully"})
    except User.DoesNotExist:
        return JsonResponse({"error": "User not found"}, status=404)