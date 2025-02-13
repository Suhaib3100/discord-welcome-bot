from flask import Flask
from threading import Thread
import os
import discord
from discord.ext import commands
from PIL import Image, ImageDraw, ImageFont, ImageOps
import requests
from io import BytesIO
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Create the output folder if it doesn't exist
if not os.path.exists('output'):
    os.makedirs('output')

# Replace with your bot token
TOKEN = os.getenv('DISCORD_TOKEN')

# Replace with your welcome channel ID
WELCOME_CHANNEL_ID = 1210950555929939988

# Path to your background image
BACKGROUND_IMAGE_PATH = 'background.png'

# Font settings (you can change the font file and size)
FONT_PATH = 'GeistMono-Regular.ttf'  # Replace with the path to your font file
FONT_SIZE = 40  # Font size for the username
WELCOME_FONT_SIZE = 35  # Smaller font size for "Welcome to the Club"
INVITER_FONT_SIZE = 30  # Smaller font size for "Invited by"
MEMBER_COUNT_FONT_SIZE = 25  # Font size for member count

# Avatar size and position
AVATAR_SIZE = 300  # Increased size
AVATAR_POSITION = (370, 80)  # Adjusted position
SHADOW_OFFSET = 10  # Increased shadow offset

# Initialize the bot
intents = discord.Intents.default()
intents.members = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Keep-alive Flask app
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is alive!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

@bot.event
async def on_ready():
    print(f'Bot is ready. Logged in as {bot.user}')

@bot.event
async def on_member_join(member):
    # Send welcome message in the welcome channel
    channel = bot.get_channel(WELCOME_CHANNEL_ID)
    if channel is None:
        print("Welcome channel not found!")
        return

    welcome_image_path = await generate_welcome_image(member)

    with open(welcome_image_path, 'rb') as f:
        picture = discord.File(f)
        await channel.send(f"Welcome to the server, {member.mention}!", file=picture)

    # Send automated DM to the new user
    await send_welcome_dm(member)

async def generate_welcome_image(member):
    # Open the background image
    background = Image.open(BACKGROUND_IMAGE_PATH).convert("RGB")
    draw = ImageDraw.Draw(background)

    # Load and process the member's avatar
    avatar_url = member.avatar.url if member.avatar else member.default_avatar.url
    response = requests.get(avatar_url)
    avatar = Image.open(BytesIO(response.content)).convert("RGB")
    avatar = avatar.resize((AVATAR_SIZE, AVATAR_SIZE))

    # Create a circular mask for the avatar
    mask = Image.new("L", (AVATAR_SIZE, AVATAR_SIZE), 0)
    draw_mask = ImageDraw.Draw(mask)
    draw_mask.ellipse((0, 0, AVATAR_SIZE, AVATAR_SIZE), fill=255)

    avatar_circle = ImageOps.fit(avatar, mask.size, centering=(0.5, 0.5))
    avatar_circle.putalpha(mask)

    # Add shadow to the avatar
    shadow = Image.new("RGBA", (AVATAR_SIZE + SHADOW_OFFSET * 2, AVATAR_SIZE + SHADOW_OFFSET * 2), (0, 0, 0, 0))
    draw_shadow = ImageDraw.Draw(shadow)
    for i in range(SHADOW_OFFSET, 0, -1):
        alpha = int(255 * (i / SHADOW_OFFSET))
        draw_shadow.ellipse((i, i, AVATAR_SIZE + SHADOW_OFFSET * 2 - i, AVATAR_SIZE + SHADOW_OFFSET * 2 - i), fill=(0, 0, 0, alpha))

    shadow_position = (AVATAR_POSITION[0] - SHADOW_OFFSET, AVATAR_POSITION[1] - SHADOW_OFFSET)
    background.paste(shadow, shadow_position, shadow)

    # Paste the avatar onto the background
    background.paste(avatar_circle, AVATAR_POSITION, avatar_circle)

    # Add "Welcome to the Club" text (smaller font size, below the avatar)
    font_welcome = ImageFont.truetype(FONT_PATH, WELCOME_FONT_SIZE)
    text_welcome = "Welcome to the Club"
    text_welcome_bbox = font_welcome.getbbox(text_welcome)
    text_welcome_width = text_welcome_bbox[2] - text_welcome_bbox[0]
    text_welcome_position = ((background.width - text_welcome_width) // 2, AVATAR_POSITION[1] + AVATAR_SIZE + 20)  # Below the avatar
    draw.text(text_welcome_position, text_welcome, font=font_welcome, fill="white")

    # Add the member's username
    font_username = ImageFont.truetype(FONT_PATH, FONT_SIZE)
    text_username = member.name
    text_username_bbox = font_username.getbbox(text_username)
    text_username_width = text_username_bbox[2] - text_username_bbox[0]
    text_username_position = ((background.width - text_username_width) // 2, text_welcome_position[1] + 50)  # Below "Welcome to the Club"
    draw.text(text_username_position, text_username, font=font_username, fill="#a1c0de")

    # Fetch the inviter (or use your user ID as default)
    inviter = await get_inviter(member)
    if inviter is None:
        inviter = bot.get_user(800265791043534848)  # Use your user ID as default

    if inviter:
        print(f"Inviter found: {inviter.name}")  # Debugging: Print the inviter's name
        # Add "Invited by" section (smaller font size)
        font_inviter = ImageFont.truetype(FONT_PATH, INVITER_FONT_SIZE)

        # Load and process the inviter's avatar
        inviter_avatar_url = inviter.avatar.url if inviter.avatar else inviter.default_avatar.url
        inviter_avatar_response = requests.get(inviter_avatar_url)
        inviter_avatar = Image.open(BytesIO(inviter_avatar_response.content)).convert("RGB")
        inviter_avatar = inviter_avatar.resize((40, 40))  # Smaller avatar size

        # Create a circular mask for the inviter's avatar
        inviter_mask = Image.new("L", (40, 40), 0)
        draw_inviter_mask = ImageDraw.Draw(inviter_mask)
        draw_inviter_mask.ellipse((0, 0, 40, 40), fill=255)

        inviter_avatar_circle = ImageOps.fit(inviter_avatar, inviter_mask.size, centering=(0.5, 0.5))
        inviter_avatar_circle.putalpha(inviter_mask)

        # Calculate positions for the "Invited by" section
        inviter_text = "Invited by"
        inviter_text_bbox = font_inviter.getbbox(inviter_text)
        inviter_text_width = inviter_text_bbox[2] - inviter_text_bbox[0]
        inviter_username_bbox = font_inviter.getbbox(inviter.name)
        inviter_username_width = inviter_username_bbox[2] - inviter_username_bbox[0]

        total_width = inviter_text_width + 50 + inviter_username_width  # 50 = spacing + avatar size
        start_x = (background.width - total_width) // 2  # Center the section horizontally
        start_y = background.height - 80  # Move slightly above the member count

        # Create a rounded rectangle background for the "Invited by" section
        rounded_rect = Image.new("RGBA", (total_width + 40, 60), (0, 0, 0, 0))
        rounded_rect_draw = ImageDraw.Draw(rounded_rect)
        rounded_rect_draw.rounded_rectangle((0, 0, total_width + 40, 60), radius=20, fill=(0, 0, 0, 128), outline="#6f6f70")

        # Paste the rounded rectangle onto the background
        rounded_rect_position = (start_x - 20, start_y - 10)
        background.paste(rounded_rect, rounded_rect_position, rounded_rect)

        # Add "Invited by" text
        draw.text((start_x, start_y), inviter_text, font=font_inviter, fill="#6f6f70")

        # Add inviter's avatar
        inviter_avatar_position = (start_x + inviter_text_width + 10, start_y - 5)
        background.paste(inviter_avatar_circle, inviter_avatar_position, inviter_avatar_circle)

        # Add inviter's username
        draw.text((start_x + inviter_text_width + 60, start_y), inviter.name, font=font_inviter, fill="#a3c2e0")
    else:
        print("No inviter found.")  # Debugging: Print if no inviter is found

    # Add member count in the bottom-right corner
    member_count = member.guild.member_count
    font_member_count = ImageFont.truetype(FONT_PATH, MEMBER_COUNT_FONT_SIZE)
    member_count_text = f"Member: #{member_count}"
    member_count_bbox = font_member_count.getbbox(member_count_text)
    member_count_width = member_count_bbox[2] - member_count_bbox[0]
    member_count_position = (background.width - member_count_width - 20, background.height - 40)  # Bottom-right corner
    draw.text(member_count_position, member_count_text, font=font_member_count, fill="white")

    # Save the final image
    output_path = f"output/welcome_{member.id}.png"
    background.save(output_path)

    return output_path

async def send_welcome_dm(member):
    # Create an embed for the welcome DM
    embed = discord.Embed(
        title="**Welcome to the Design Engineers Club!**",
        description=(
            f"Hi {member.mention}\n"
            "Thanks for joining the Design Engineers Club!\n\n"
            "To get started, please introduce yourself in #👋┃intro.\n\n"
            "Here's what you can do in the community:\n"
            "❖ Get support on Once UI: We're here to help you get started with bringing your vision into reality.\n"
            "❖ Get feedback on your projects or portfolio: We're a constructive bunch, so share freely.\n"
            "❖ Share inspiration and learn from others: Came across a useful resource? Share it with us!"
        ),
        color=discord.Color.blue()
    )

    # Attach the image to the embed
    file = discord.File("image.png", filename="image.png")
    embed.set_image(url="attachment://image.png")

    try:
        # Send the DM
        await member.send(file=file, embed=embed)
        print(f"Welcome DM sent to {member.name}")
    except discord.Forbidden:
        print(f"Could not send DM to {member.name}. They may have DMs disabled.")

async def get_inviter(member):
    # Fetch the audit logs to find the inviter
    try:
        async for entry in member.guild.audit_logs(action=discord.AuditLogAction.invite_create, limit=10):
            if entry.target == member:
                return entry.user
    except discord.Forbidden:
        print("Bot does not have permission to view audit logs.")  # Debugging: Print if permissions are missing
    return None

# Start the keep-alive server
keep_alive()

# Run the bot
bot.run(TOKEN)