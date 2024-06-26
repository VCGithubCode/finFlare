from django.shortcuts import render, get_object_or_404, redirect
from django.conf import settings
from django.urls import reverse
import requests
from django.contrib import messages
from .models import UserAccountPortfolio, StockBalance, Transaction, Stock
from decimal import Decimal

####################################################
#### API serpapi view functions - Fetching Data ####
####################################################
def get_market_data(api_key, category, max_items=5):
    """
    Fetch market data using SerpApi for a specified category
    """
    base_url = "https://serpapi.com/search.json"
    category = 'us' if category == 'Stocks US' else category.lower()
    symbols = {
        'us': ['DJI:INDEXDJX', 'SPX:INDEXSP', 'COMP:INDEXNASDAQ', 'RUT:INDEXRUS', 'VIX:INDEXCBOE'],
        'crypto': ['BTC:USD', 'ETH:USD', 'ADA:USD', 'XRP:USD', 'DOGE:USD'],
        'currencies': ['EUR:USD', 'USD:JPY', 'GBP:USD', 'USD:CAD', 'AUD:USD'],
        'futures': ['YMW00:CBOT', 'ESW00:CME_EMINIS', 'NQW00:CME_EMINIS', 'GCW00:COMEX', 'CLW00:NYMEX'],
    }

    symbols_list = symbols.get(category, [])
    market_data_list = []

    for symbol in symbols_list:
        params = {
            'engine': 'google_finance',
            'q': symbol,
            'api_key': api_key
        }

        response = requests.get(base_url, params=params)
        data = response.json()

        market_info_list = data.get('markets', {}).get(category.lower(), [])

        for market_info in market_info_list:
            market_data_list.append({
                'symbol': symbol.split(':')[0],
                'name': market_info.get('name', ''),
                'price': market_info.get('price', ''),
                'price_movement': {
                    'movement': market_info.get('price_movement', {}).get('movement', ''),
                    'percentage': market_info.get('price_movement', {}).get('percentage', 0),
                },
            })

        if len(market_info_list) >= max_items:
            break

    return market_data_list


def stock_data(request):
    """
    View function for displaying market data
    """
    api_key = settings.API_KEY
    categories = ['Stocks US', 'Crypto', 'Currencies', 'Futures']

    selected_category = 'Stocks US'  # Default category

    if request.method == 'POST':
        selected_category = request.POST.get('stockSelector', selected_category)

    combined_data = {
        selected_category: get_market_data(api_key, selected_category),
    }    

    # wallet display values
    user = request.user    
    try: 
        user_portfolio = UserAccountPortfolio.objects.get(user=user)
        balance = user_portfolio.balance
        
        user_portfolio = UserAccountPortfolio.objects.get(user=request.user)
        open_positions = StockBalance.objects.filter(user=user_portfolio, is_buy_position=True)
    
        stock_names = []
        stock_quantities = []

        for position in open_positions:
            stock_names.append(position.stock)
            stock_quantities.append(position.quantity)   

        context = {
            'balance': balance,
            'stock_names': stock_names,
            'stock_quantities': stock_quantities,
        } 

    except: 
        context = {
            'balance': 10000.0,
            'stock_names': [],
            'stock_quantities': [],
        }
    
    return render(request, 'markets/markets.html', {
        'combined_data': combined_data, 
        'selected_category': selected_category, 
        'categories': categories, 
        **context })
###################################################
#### API serpapi view functions - ENDS HERE #######
###################################################

def thank_you(request):
    return render(request, 'markets/thank_you.html')

def trade_stock(request):
    selected_category = 'Stocks US'
    context = {}

    try:
        if request.method == 'POST':
            user_profile = UserAccountPortfolio.objects.get(user=request.user)
            name = request.POST.get('name')

            quantity_str = request.POST.get('quantitySelector')
            if not quantity_str or not quantity_str.isdigit():
                messages.error(request, f"Invalid quantity: {quantity_str}")
                return render(request, 'markets/markets.html')         

            quantity = int(quantity_str)

            price = Decimal(request.POST.get('price'))
            transaction_type = request.POST.get('transaction_type')

            # Check if enough balance 
            if transaction_type == 'BUY':
                total_cost = quantity * price
                if user_profile.balance < total_cost:
                    messages.error(request, "Insufficient funds to complete the purchase. Please try again.")
                    return redirect('trade_stock')  # Redirect to the same view on error

                transaction = Transaction.objects.create(
                    user_profile=user_profile,
                    name=name,
                    quantity=quantity,
                    price=price,
                    transaction_type=transaction_type,
                )

                # Update the user's account balance and update the buy position
                if transaction_type == 'BUY':
                    user_profile.balance -= total_cost
                    user_profile.save()

                    # Find the matching buy position to update
                    buy_position = StockBalance.objects.filter(
                        user=user_profile,
                        stock=name,
                        is_buy_position=True,
                    ).first()

                    if buy_position is None:
                        buy_position = StockBalance.objects.create(
                            user=user_profile,
                            stock=name,
                            quantity=quantity,
                            purchase_price=price,
                            is_buy_position=True,
                        )

                    buy_position.save()

                    if buy_position.quantity == 0:
                        messages.success(request, f"You have successfully bought and sold {quantity} shares of {name}.")
                    else:
                        messages.success(request, f"You have partially sold {quantity} shares of {name}.")

                    # Redirect to the "thank you" page upon a successful sale
                    return render(request, 'markets/thank_you.html')

                elif transaction_type == 'SELL':
                    total_cost = quantity * price
                    sell_position = StockBalance.objects.get(
                        user=user_profile,
                        stock=name,
                        is_buy_position=True,
                    )
                    
                    user_profile.balance += quantity * price
                    user_profile.save()

                    sell_position.delete()

                    messages.success(request, f"You have successfully sold the position of {name}.")
                    
                    # Redirect to the "thank you" page upon a successful sale
                    return render(request, 'markets/thank_you.html')

            # Update the context with the latest data
            user_portfolio = UserAccountPortfolio.objects.get(user=request.user)
            balance = user_portfolio.balance
            open_positions = StockBalance.objects.filter(user=user_portfolio, is_buy_position=True)

            stock_names = []
            stock_quantities = []

            for position in open_positions:
                stock_names.append(position.stock)
                stock_quantities.append(position.quantity)

            context = {
                'balance': balance,
                'stock_names': stock_names,
                'stock_quantities': stock_quantities,
            }

            # Pass the updated context when rendering the template
            return render(request, 'markets/markets.html', {
                'combined_data': get_market_data(settings.API_KEY, 'Stocks US'),
                'selected_category': 'Stocks US',
                'categories': ['Stocks US', 'Crypto', 'Currencies', 'Futures'],
                **context,
            })

    except: 
        context = {
            'balance': 10000.0,
            'stock_names': [],
            'stock_quantities': [],
        }

    return render(request, 'markets/markets.html', {
        'combined_data': get_market_data(settings.API_KEY, selected_category),
        'selected_category': selected_category,
        'categories': ['Stocks US', 'Crypto', 'Currencies', 'Futures'],
        **context,
    })


