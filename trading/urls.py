from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from trading.views import buy_stock, sell_stock, stock_holdings,all_users_holdings
from trading.views import update_user_balance,net_portfolio_value,all_users_portfolio_value,create_user
from trading.views import delete_user
urlpatterns = [
    path('login/', TokenObtainPairView.as_view(), name='token_obtain_pair'),  # Get access token
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),  # Refresh token
    path('buy/', buy_stock, name='buy_stock'),
    path('sell/', sell_stock, name='sell_stock'),
    path('holdings/', stock_holdings, name='stock_holdings'),  # New API to check holdings
    path("admin/all_holdings/", all_users_holdings, name="all_users_holdings"),
    path("admin/update_balance/", update_user_balance, name="update_user_balance"),
    path("value/",net_portfolio_value,name="net_portfolio_value"),
    path("admin/value/",all_users_portfolio_value,name="all_users_portfolio_value"),
    path("admin/create_user/",create_user,name="create_user"),
    path("admin/delete_user/",delete_user,name="delete_user")
]