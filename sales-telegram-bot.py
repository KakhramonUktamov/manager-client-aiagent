import os
import requests
from telethon import TelegramClient, events
import asyncio
import schedule
import time
from threading import Thread

# Configuration
api_id = int(os.getenv('TG_API_ID', '27884296'))
api_hash = os.getenv('TG_API_HASH', 'a21afca4722ba67d1605ef90ef22c511')
phone = os.getenv('TG_PHONE', '+998947774570')

# Sales managers' usernames or user IDs
sales_managers = [
    {'username': 'Qahramon_Uktamov', 'user_id': None},
    {'username': 'nisanbaev', 'user_id': None},
    # Add more managers as needed
]

# N8N webhook URLs
n8n_get_clients_url = os.getenv('N8N_GET_CLIENTS_URL', 'https://kakhramon.app.n8n.cloud/webhook/get_overdue_clients')
n8n_manager_response_url = os.getenv('N8N_MANAGER_RESPONSE_URL', 'https://kakhramon.app.n8n.cloud/webhook/manager_response')

# Days threshold for overdue clients
DAYS_THRESHOLD = int(os.getenv('DAYS_THRESHOLD', '30'))

client = TelegramClient('sales_bot_session', api_id, api_hash)
manager_histories = {}
overdue_clients_cache = {}

def get_overdue_clients_and_send():
    """Fetch overdue clients from n8n and send to managers"""
    try:
        print("Fetching overdue clients...")
        response = requests.post(n8n_get_clients_url, json={
            "days_threshold": DAYS_THRESHOLD
        }, timeout=30)
        
        data = response.json()
        message = data.get("message", "")
        overdue_clients = data.get("overdue_clients", [])
        
        if overdue_clients:
            # Cache the overdue clients for later reference
            overdue_clients_cache['current'] = overdue_clients
            
            # Send to all managers
            asyncio.run_coroutine_threadsafe(
                send_to_managers(message), 
                client.loop
            )
            print(f"Sent overdue clients list to {len(sales_managers)} managers")
        else:
            print("No overdue clients found")
            
    except Exception as e:
        print(f"Error fetching overdue clients: {e}")

async def send_to_managers(message):
    """Send message to all sales managers"""
    for manager in sales_managers:
        try:
            if manager['user_id']:
                await client.send_message(manager['user_id'], message, parse_mode='markdown')
            else:
                await client.send_message(manager['username'], message, parse_mode='markdown')
            
            # Small delay between messages
            await asyncio.sleep(1)
            
        except Exception as e:
            print(f"Error sending to manager {manager['username']}: {e}")

@client.on(events.NewMessage(incoming=True))
async def handle_manager_response(event):
    """Handle responses from sales managers"""
    if not event.is_private:
        return
    
    user_id = event.sender_id
    text = event.text
    username = getattr(await event.get_sender(), "username", None)
    
    # Check if the sender is a sales manager
    is_manager = False
    for manager in sales_managers:
        if (manager.get('user_id') == user_id or 
            manager.get('username') == username):
            is_manager = True
            # Update user_id if we only had username
            if not manager.get('user_id'):
                manager['user_id'] = user_id
            break
    
    if not is_manager:
        # Ignore messages from non-managers
        return
    
    # Initialize chat history for this manager
    if user_id not in manager_histories:
        manager_histories[user_id] = []
    
    # Add manager's message to history
    manager_histories[user_id].append({"manager": text})
    
    # Prepare payload for n8n
    payload = {
        "manager_id": user_id,
        "username": username,
        "chat_history": manager_histories[user_id],
        "overdue_clients": overdue_clients_cache.get('current', [])
    }
    
    try:
        # Send to n8n for processing
        response = requests.post(n8n_manager_response_url, json=payload, timeout=30)
        resp_data = response.json()
        
        reply = resp_data.get("reply", "Rahmat!")
        called_client = resp_data.get("called_client")
        
        # Add bot's response to history
        manager_histories[user_id][-1]["assistant"] = reply
        
        # Send reply to manager
        await asyncio.sleep(1)  # Small delay to feel more natural
        await event.respond(reply)
        
        # Log if a client status was updated
        if called_client:
            print(f"Manager {username} called client: {called_client}")
        
    except Exception as e:
        print(f"Error processing manager response: {e}")
        await event.respond("Kechirasiz, texnik muammo yuz berdi. Iltimos, keyinroq urinib ko'ring.")

def run_scheduler():
    """Run the scheduler in a separate thread"""
    while True:
        schedule.run_pending()
        time.sleep(1)  # Check every minute

async def main():
    """Main function to start the bot"""
    await client.start(phone=phone)
    print("Sales follow-up bot started!")
    
    # Set up scheduling
    # schedule.every().day.at("09:00").do(get_overdue_clients_and_send)  # Daily at 9 AM
    # schedule.every().monday.at("08:30").do(get_overdue_clients_and_send)  # Monday morning
    
    # You can also trigger manually for testing
    # schedule.every(30).minutes.do(get_overdue_clients_and_send)  # Every 30 minutes for testing
    get_overdue_clients_and_send()
    # Start scheduler in separate thread
    # scheduler_thread = Thread(target=run_scheduler, daemon=True)
    # scheduler_thread.start()
    
    print("Scheduler started. Bot is ready to handle manager responses.")
    print("Scheduled to send client lists:")
    print("- Daily at 9:00 AM")
    print("- Every Monday at 8:30 AM")
    
    # Send initial message (optional, for testing)
    # get_overdue_clients_and_send()
    
    # Keep the bot running
    await client.run_until_disconnected()

if __name__ == "__main__":
    with client:
        client.loop.run_until_complete(main())
