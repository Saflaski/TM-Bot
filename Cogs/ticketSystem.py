import discord
import pymongo
import datetime
import time
import re
import json
import asyncio
import string
import secrets
import re
from os import environ
from discord.ext import commands, tasks

#settingup MongoDB
mongoCredURL = environ["MONGODB_PASS"]
myclient = pymongo.MongoClient(mongoCredURL)
db = myclient["SAR6C_DB"]
dbCol = db["users_col"]
matchesCol = db["matches_col"]
ticketsCol = db["tickets_col"]

#Global Variables
baseELO = 2000
embedSideColor = 0x2425A2
embedTitleColor = 0xF64C72
footerText = "SAR6C | Use .h for help!"
footerIcoURL = "https://media.discordapp.net/attachments/822432464290054174/832871738030817290/sar6c1.png"
thumbnailURL = "https://media.discordapp.net/attachments/822432464290054174/832871738030817290/sar6c1.png"

#Global variables
ticketTimeOut = 180		#Timeout for auto cancelling a ticket due to AFK
ticketAlert = 10		#Interval for refreshing ticket channel name to alert admins
check_mark = '\u2705'

#Discord Values
with open("ServerInfo.json") as jsonFile:
    discServInfo = json.load(jsonFile)

discTextChannels = discServInfo["TextChannels"]
infoRegTC = discTextChannels["helpRegInfo"]
helpDeskTC = discTextChannels["help"]
queueTC = discTextChannels["queue"]
matchGenTC = discTextChannels["matchGen"]
postMatchTC = discTextChannels["postMatch"]
ticketsTC = discTextChannels["tickets"]
completeChannelList = [postMatchTC, helpDeskTC, ticketsTC]

#Roles
adminRole = "R6C Admin"
userRole = "R6C"


class TicketSystem(commands.Cog):

	def __init__(self, client):
		self.client = client

	@commands.Cog.listener()
	async def on_ready(self):
		print('Cog: "ticketSystem" is ready.')
		self.autoTicketCHUpdate.start()

	#Channel Checks
	def checkCorrectChannel(channelID = None, channelIDList = []):
		def function_wrapper(ctx):
			givenChannelID = ctx.message.channel.id
			if givenChannelID in channelIDList or givenChannelID == channelID:
				return True
			else:
				return False
		return commands.check(function_wrapper)

	@commands.has_any_role(userRole, adminRole)
	@commands.command(name = "openticket")
	@checkCorrectChannel(channelIDList = completeChannelList)
	async def openTicket(self, ctx):
		
		#DM the user
		playerObj = ctx.author

		timeout = ticketTimeOut			#Gets time limit
		ticketID = ""
		prepMsg = 	(
					"__**Preparing Ticket**__"

					"\nPlease enter a valid subject/title **OR** alternatively" 
					" choose (copy-paste) one of the following options"
					" *(you can give a description after this step)*:"
					)

		subjectOptions = (
						"```\n"
						"Report Player for Cheating\n"
						"Report Player for High Ping\n"
						"Report Player for Toxicity\n"
						"Report Player Absence\n"
						"Report Player for other reasons\n"
						"Report Delay in Lobby Formation\n"
						"Report Match Fixing\n"
						"```"
						)
		cancelNote = "*Note: You can use* `cancel` *at anytime of the ticket process to cancel the ticket*"


		dmMsg = await playerObj.send(prepMsg)
		await playerObj.send(f"{subjectOptions}\n{cancelNote}")

		def checkIfAuthorDM(message):					#Only accepting messages from the author's DMs
			
			if message.channel == dmMsg.channel and message.author != dmMsg.author:			#To not capture bot's messages
				return True
			else:
				return False
			

		async def checkIfCancel(message):				#Check if user used cancel
			if message.content.lower() == "cancel":
				await playerObj.send("*Ticket Cancelled. Use* `.openticket` *in the server's channel to open a new ticket*")
				return True
			else:
				return False



		def getEvidence(msg):							#Check if message either has an attachment or a URL
			if len(msg.attachments) != 0:
				for attachment in msg.attachments:
					return [attachment.url, ]			#Caller needs a list yo
			elif urlFinder(msg.content):
				return urlFinder(msg.content)			#Returns list of URLs, returns False if none found
			else:
				return None
			
		
		async def generateTicket(pendingConf = True):

			#Get UTC Date and Time
			ticDateTime = datetime.datetime.utcnow().replace(microsecond= 0)

			#Get Author
			tickAuth = str(playerObj)

			#Generate Ticket Embed
			ticketEmbed = genTicketEmbed(ticketID, tickAuth, ticketSubject, ticketDesc, ticketEvidences, ticDateTime)
			await playerObj.send(content = "Generated Ticket", embed = ticketEmbed)
			ticketsChannel = self.client.get_channel(ticketsTC)
			await ticketsChannel.send(content = "New Ticket", embed = ticketEmbed)
			
			#Upload a new ticket to MongoDB
			try:
				ticketsCol.insert_one({"Id": ticketID, "Auth": tickAuth, "Sub": ticketSubject, 
								"Desc": ticketDesc, "Evid": ticketEvidences, "Datetime" : ticDateTime,
								"Status": "Open", "Remarks" : "None"})			#Remarks field is for remarks or comments by an admin
			except Exception as e:
				print(f"Openticket MongoDB Error: {e}")

		currentStage = 1

		ticketSubject = ""
		ticketDesc = ""
		ticketEvidences = []
		totalStringLength = ""			#For attachments embed as it has a max length of 1024 chars

		while currentStage <= 3:
			try:
				authorReply = await self.client.wait_for('message', timeout = timeout, check = checkIfAuthorDM)
			except asyncio.TimeoutError:
				await playerObj.send("Ticket cancelled due to timeout (2 minutes crossed since last message)."
									" Use `.openticket` in the server's channel to open a new ticket")
				return

			if await checkIfCancel(authorReply):
				return
			
			if currentStage == 1:
				ticketSubject = authorReply.content
				if len(ticketSubject) < 10 or len(ticketSubject) > 900:
					await playerObj.send("Ticket Subject Length inadequate or too large")
				else:
					#Upload to DB
					await playerObj.send("Please enter a complete description of the problem, try "
										"to include as much info as possible (eg. Discord IDs, uPlay IGNs)."
										"\nYou can add proofs/evidences as attachments later."
										" To skip current step, use `none`")
					currentStage += 1
			
			elif currentStage == 2:
				ticketDesc = authorReply.content
				
				if (len(ticketDesc) > 10 or ticketDesc.lower() == "none") and len(ticketDesc) < 900:		#Checks if valid length or if it's none
					if ticketDesc.lower() == "none":
						ticketDesc = ticketDesc.lower().capitalize()		#Purely cosmetic purposes					
					currentStage += 1
					#Send instructions for attachments
					await playerObj.send("You can now add attachments or add links. To stop attaching or"
										" if you want to skip this step, use `done`")
				else:
					await playerObj.send("Inadequate description length, try again.")
				

			elif currentStage == 3:
				try:
					if authorReply.content.lower() == "done":
						ticketID = genTicketID()
						await generateTicket()		#show embed of ticket and upload to DB
						currentStage += 1

					elif getEvidence(authorReply) is not None:
						evidenceList = getEvidence(authorReply)
						
						if len(totalStringLength) < 850:
							for evidence in evidenceList:
								ticketEvidences.append(evidence)
								totalStringLength += evidence
							await authorReply.add_reaction(check_mark)
							
						else:
							await playerObj.send("You're trying to add too many links, please use "
												"a cloud-storage platform (eg. G-drive shareable link) or "
												"create a separate ticket referencing this ticket in the subject line")

						#ticketEvidences.append(getEvidence(authorReply))
					else:
						await playerObj.send("You didn't attach anything relevant, try again.")

				except Exception as e:
					print(e)
		


	@openTicket.error
	async def openTicketError(self, ctx, error):
		if isinstance(error, commands.CheckFailure):
			pass

	@commands.has_any_role(userRole, adminRole)
	@commands.command(name = "findticket")
	@checkCorrectChannel(channelIDList = completeChannelList)
	async def findTicket(self, ctx, matchID):
		
		queryResult = ticketsCol.find_one({"Id" : matchID})
		if queryResult is not None:
			ticID = matchID
			ticAuth = queryResult["Auth"]
			ticSub = queryResult["Sub"]
			ticDesc = queryResult["Desc"]
			ticEvid = queryResult["Evid"]
			ticDateTime = queryResult["Datetime"]
			ticStat = queryResult["Status"]
			ticRemarks = queryResult["Remarks"]
		
			ticketEmbed = genTicketEmbed(ticID, ticAuth, ticSub, ticDesc,
						ticEvid, ticDateTime, ticStat, ticRemarks)
			await ctx.send(embed = ticketEmbed)
			
		else:
			await ctx.send("Ticket not found")

	@findTicket.error
	async def findTicketError(self, ctx, error):
		if isinstance(error, commands.CheckFailure):
			pass
		elif isinstance(error, commands.MissingRequiredArgument):
			await ctx.send("Try `.findticket <match ID>` without <>")

	@commands.has_any_role(adminRole)
	@commands.command(name = "findopentickets")
	@checkCorrectChannel(channelIDList = completeChannelList)
	async def findOpenTickets(self, ctx):

		#Find all tickets that are open
		openTickets = ticketsCol.find({"Status": "Open"}, {"Id" : 1, "Auth": 1, "Datetime": 1, "Sub": 1}).sort([("Datetime", -1)])

		descText = ""
		ticketCount = 1
		if openTickets is not None:
			for ticket in openTickets:
				ticketID = ticket['Id']
				ticketAuth = ticket['Auth']
				ticketSub = ticket['Sub']
				if len(ticketSub) > 100:
					ticketSub = ticketSub[:100] + "..."
				descText += f"**{ticketCount}. ID: `{ticketID}` | Auth: `{ticketAuth}`**\nSubject: {ticketSub}\n\n"
				ticketCount += 1

		else:
			descText = "No open tickets"

		embed = discord.Embed(title = "Open Tickets", description = descText, color = embedSideColor)
		await ctx.send(embed = embed)

	@findOpenTickets.error
	async def findOpenTicketsError(self, ctx, error):
		if isinstance(error, commands.CheckFailure):
			pass

	@commands.has_any_role(adminRole)
	@commands.command(name = "closeticket")
	@checkCorrectChannel(channelIDList = completeChannelList)
	async def closeTicket(self, ctx, matchID, givenRemark = "None"):

		

		queryResult = ticketsCol.find_one_and_update({"Id" : matchID}, {'$set' : {"Status" : "Closed",
														"Remarks" : givenRemark}}
													)
		if queryResult is not None:
			ticID = matchID
			ticAuth = queryResult["Auth"]
			ticSub = queryResult["Sub"]
			ticDesc = queryResult["Desc"]
			ticEvid = queryResult["Evid"]
			ticDateTime = queryResult["Datetime"]
			ticStat = "Closed"
			ticRemarks = givenRemark
		
			ticketEmbed = genTicketEmbed(ticID, ticAuth, ticSub, ticDesc,
						ticEvid, ticDateTime, ticStat, ticRemarks)
			await ctx.send(embed = ticketEmbed)

		else:
			await ctx.send("Ticket not found")

	@closeTicket.error
	async def closeTicketError(self, ctx, error):
		if isinstance(error, commands.CheckFailure):
			pass
		elif isinstance(error, commands.MissingRequiredArgument):
			await ctx.send("Try `.closeticket <match ID> <remarks>` without <>")

	@tasks.loop(seconds = ticketAlert)
	async def autoTicketCHUpdate(self):
		#Count all open tickets

		ticketNum = ticketsCol.count_documents({"Status" : "Open"})
		if ticketNum != 0:
			chNameString = f"🔴-{ticketNum}"
		else:
			chNameString = f"🟢"
		ticketChannel = await self.client.fetch_channel(ticketsTC)
		newChannelName = f"r6s-tickets-{chNameString}"
		await ticketChannel.edit(name = newChannelName)




def genTicketID():
    """
    Generates unique alphanumeric token of length 8
    Total possible permutations: (26 + 26 + 10) ^ 8
    Therefore, collision probability is at 50% only at 62^4

    """
    alphabet = string.ascii_letters + string.digits
    ticketID = ''.join(secrets.choice(alphabet) for i in range(6))
    return ticketID

def urlFinder(givenString):					#Tries to find valid URLs
	regex = re.compile(
			"(((http|https)://)(www.)?" +
			"[a-zA-Z0-9@:%._\\+~#?&//=]" +
			"{2,256}\\.[a-z]" +
			"{2,6}\\b([-a-zA-Z0-9@:%" +
			"._\\+~#?&//=]*))", re.IGNORECASE)

	if len(regex.findall(givenString)) != 0:
		pass
		URLs = []
		for url in regex.findall(givenString):
			URLs.append(url[0])
		return URLs							#Returns a list of URLs if found
	else:
		return False

def genTicketEmbed(ticketID, ticAuth, ticSubject, ticDesc, ticEvidArr, ticDateTime = None, ticStat = "Open", ticRemarks = "None"):


	#Link Sorting
	#ticketEvidenceDict = {}
	ytLinkCounter = 1
	discAttCounter = 1
	otherLinkCounter = 1
	ytEvidStr = ""
	otherEvidStr = ""
	discEvidStr = ""

	if len(ticEvidArr) != 0:
		for evidence in ticEvidArr:
			if "youtube" in evidence or "youtu.be" in evidence:
				#ticketEvidenceDict[f"YT Link {ytLinkCounter}"] = ticEvidArr[evidence]
				ytEvidStr += f"[YT Link {ytLinkCounter}]({evidence})\n"
				ytLinkCounter += 1
			elif "discordapp" in evidence:
				#ticketEvidenceDict[f"Discord Attachment {discAttCounter}"] = ticEvidArr[evidence]
				discEvidStr += f"[Attachment {discAttCounter}]({evidence})\n"
				discAttCounter += 1
			else :
				#ticketEvidenceDict[f"Other link {otherLinkCounter}"] = ticEvidArr[evidence]
				otherEvidStr += f"[Other link {otherLinkCounter}]({evidence})\n"
				otherLinkCounter += 1
	else:
		otherEvidStr = "None"
	if ticStat == "Open":
		embedColor = 0xFF4500
	else:
		embedColor = 0x00FF00


	ticketEmbed=discord.Embed(title="SAR6C Ticket",
							description=f"Subject: {ticSubject}\nID: `{ticketID}`\nAuthor: {ticAuth}", 
							color=embedColor, timestamp = ticDateTime)
	ticketEmbed.add_field(name="Description", value=ticDesc, inline = False)
	ticketEmbed.add_field(name="Evidences Provided", value= "".join([ytEvidStr, discEvidStr, otherEvidStr]), inline = False)
	ticketEmbed.add_field(name = "Status", value = ticStat, inline = False)
	if ticRemarks != "None":
		ticketEmbed.add_field(name = "Remarks", value = ticRemarks, inline = False)
	ticketEmbed.set_footer(text = f"Local time when ticket generated - ", icon_url = footerIcoURL)
	
	return ticketEmbed


def setup(client):
	client.add_cog(TicketSystem(client))
