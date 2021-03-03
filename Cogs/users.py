import discord
import pymongo
import datetime
import re
from discord.ext import commands

#settingup MongoDB
myclient = pymongo.MongoClient("mongodb+srv://SFSI1:JJJQb7a9hHNbiYw@cluster0.9oihh.mongodb.net/TM_DB?retryWrites=true&w=majority")
db = myclient["TM_DB"]
dbCol = db["users_col"]

#Global Variables
baseELO = 2000
embedSideColor = 0x2425A2
embedTitleColor = 0xF64C72
footerText = "R6TM Bot v0.1 | Use .h for help!"
footerIcoURL = "https://cdn.discordapp.com/attachments/813715902028840971/813716545627881482/idk.png"
thumbnailURL = "https://media.discordapp.net/attachments/780358458993672202/785365594714275840/APAC_SOUTH_LOGO.png"


class Users(commands.Cog):

	def __init__(self, client):
		self.client = client

	@commands.Cog.listener()
	async def on_ready(self):
		print('Cog: "users" is ready.')

	#Register user
	@commands.command(name = "register")
	@commands.guild_only()
	async def registerUser(self, ctx, uplayIGN):
		
		print(f"{ctx.author} used register")

		author = ctx.author
		
		#Logging purposes
		print(f"Author: {author.name}#{author.discriminator} requested to register.\nAuthor's ID: {author.id}")

		#await ctx.send(f"{type(author)} is straight. {type(str(author))} is str") #Ignore
		

		if dbCol.find_one({"discID": author.id}):				#Checks if user is already registered
			await ctx.send(f'\N{Cross Mark} {author} is already registered!')
		
		else:													#If not registered, prepares dictionary for mongodb insert
			tempDict = 	{	"discID": author.id ,								
							"discName" : f"{str(author)}" ,						
							"dateRegistered" : datetime.datetime.now(),			
							"uplayIGN" : uplayIGN,								
							"ELO" : baseELO,									
						}
			try:						#Inserts data
				x = dbCol.insert_one(tempDict)
				await ctx.send(f"\N{White Heavy Check Mark} {author} succesfully registered!")
				print(f" {author} succesfully registered. ID: {x.inserted_id}")
			except:
				await ctx.send("Error: Contact admin")			
				print(f"Failed to register user: {author}")
		
	@registerUser.error
	async def register_error(self, ctx, error):
		if isinstance(error, commands.MissingRequiredArgument):
			await ctx.send('Usage: ".register <Uplay Username>" Eg. ".register F.lanker"')
		if isinstance(error, commands.NoPrivateMessage):
			pass		#To prevent clogging up terminal



	#@commands.command(name = "test")
	#async def testCommand(self, ctx, tier = 3):

	
	@commands.command(name = "info")
	@commands.guild_only()
	async def getUserInfo(self, ctx, givenID = ""):
		
		print(f"{ctx.author} used info")

		myRegex = re.compile("<.*\d{18}>$")				#Discord ID format is <!@000000000000000000>
		rawList = myRegex.findall(givenID)				#Performs regex search to see if Discord ID was included

		if len(rawList) == 1:							#@DiscordID mode
			
			givenID = int(str(givenID)[3:-1])			#convert from <!@######> to ###### ;# is digit
			print(f"@Discord mode: {givenID}")
			mydoc = dbCol.find({"discID" : givenID})

		elif len(givenID) == 0:							#Self mode
			
			print(f"Self mode: {ctx.author.id}")
			givenID = ctx.author.id
			mydoc = dbCol.find({"discID" : givenID})

		elif len(givenID) >=0 :							#Uplay mode
			
			print(f"Uplay mode: {ctx.author.id}")
			mydoc = dbCol.find({"uplayIGN" : givenID})

		userDiscName = ""		#Later used to check if data extracted successfully

		#Extract Data from collection
		for x in mydoc:									
			try:

				userDiscName = x["discName"]
				userUplayID = x["uplayIGN"]
				userELO = x["ELO"]

				userJoinDate = x["dateRegistered"]
				userJoinDate = userJoinDate.date()

			except:
					print("Error: At Try/Except at .info ")

		#Creates embed object if data has been succesfully extracted, otherwise says "User not found"
		if len(userDiscName) != 0:

			myEmbed = discord.Embed(title = f"{userDiscName}", color = embedSideColor)
			myEmbed.add_field(name = "Uplay ID: ", value = userUplayID, inline = True)		
			myEmbed.add_field(name = "ELO: ", value = userELO, inline = True)
			myEmbed.add_field(name = "Join Date:", value = userJoinDate, inline = False)
			myEmbed.set_footer(text = footerText, icon_url = footerIcoURL)
			await ctx.send(embed = myEmbed)

		else:
			await ctx.send("User not found.")

		
	
	@getUserInfo.error
	async def info_retrieve_error(self, ctx, error):
		if isinstance(error, commands.NoPrivateMessage):
			pass		#To prevent clogging up terminal
		elif isinstance(error, commands.MissingRequiredArgument):
			await ctx.send("Usage: .info <@DiscordID> | Eg.: .info @Carl\nOptional uplayID search mode: .info <uplayID> uplay| Eg.: .info Pengu.G2 uplay")
		else:
			print("Error: info_retrieve_error")

	#Forceregister is basically the same as .register except only for high-permission users/admins
	@commands.command(name = "forceregister")
	@commands.has_permissions(ban_members=True) 		#To be changed to match a certain role or higher when deployed
	async def forceRegister(self, ctx, member: discord.Member, uplayIGN, startingELO = baseELO):


		print(f"{ctx.author} used forceregister")

		discID = member.id

		if dbCol.find_one({"discID": discID}) is not None:							#Checks if user is already registered
			await ctx.send(f'\N{Cross Mark} {member} is already registered!')
		else:
			tempDict = 	{	"discID": discID ,									#
							"discName" : f"{str(member)}" ,						#
							"dateRegistered" : datetime.datetime.now(),			#
							"uplayIGN" : uplayIGN,								#
							"ELO" : startingELO,								#
						}
			try:
				x = dbCol.insert_one(tempDict)
				await ctx.send(f"\N{White Heavy Check Mark} {member} succesfully force-registered!")
				print(f"{member} succesfully registered. ID: {x.inserted_id}, uplay: {uplayIGN}, ELO:{startingELO}")
			except:
				await ctx.send("Error: Contact admin")			#Let's pray this doesn't happen 
				print(f"Failed to register user: {member}")
		
		
	@forceRegister.error
	async def register_error(self, ctx, error):
		if isinstance(error, commands.MissingRequiredArgument):
			await ctx.send('Usage: !forceregister <@discordID> <uplayID> <startingELO>')


	#Updates Uplay ID
	@commands.command(aliases = ["updateUplay", "uUplay", "updateuplay", "uuplay"])
	async def update_Uplay(self, ctx, newUplayID):

		authorID = ctx.author.id

		myQuery = {"discID" : authorID}					#To query database based on author's discord ID
		targetUpdate = {"uplayIGN" : newUplayID}		#Preps dictionary for MongoDB update

		myDoc = dbCol.find_one(myQuery)					#

		op_status = dbCol.update_one(myQuery, { '$set': targetUpdate})		#If you know how to use op_status to-
																			#check if op was succesful, do add.

		print(f"{ctx.author} requested to change uplayID to {newUplayID}")	#logging


		#Creates embed object
		myEmbed = discord.Embed(title = "Changed Uplay ID", color = embedSideColor)
		myEmbed.add_field(name = "Previous Uplay ID:", value = myDoc["uplayIGN"], inline = False)
		myEmbed.add_field(name = "Requested Uplay ID:", value = newUplayID, inline = False)
		await ctx.send(embed = myEmbed)

	
def setup(client):
	client.add_cog(Users(client))