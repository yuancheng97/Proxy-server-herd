import sys,asyncio,json,time
from aiohttp import ClientSession

port = {"Hill": 11995,"Jaquez": 11996, "Smith": 11997, "Campbell":11998, "Singleton":11999}
neighbor = {
	"Hill": ["Jaquez", "Smith"],
	"Jaquez": ["Hill","Singleton"],
	"Smith": ["Hill", "Singleton","Campbell"],
	"Singleton": ["Jaquez","Smith","Campbell"],
	"Campbell": ["Smith","Singleton"]
}
timestamp = set()
client_position = {}
client_time = {}
client_timediff = {}
first_server = {}
API_key = "*"
base_url = '*'

def isfloat(string):
	try:
		float(string)
		return True
	except ValueError:
		return False

def findLocation(location):
	if location[0] not in '+-':
		return (-1,-1)
	pos = location[1:].find('+')
	if pos == -1:
		pos = location[1:].find('-')
		if pos == -1:
			return (-1,-1)

	if not (isfloat(location[0:pos+1]) and isfloat(location[pos+1:])):
		return (-1,-1)
	else:
		return (location[0:pos+1],location[pos+1:])


def validate(message):
	if message[0] != 'IAMAT' and message[0] != 'WHATSAT' and message[0] != 'FLOOD':
		return False
	elif message[0] == 'IAMAT':
		if not isfloat(message[3]):
			return False
		elif findLocation(message[2]) == (-1,-1):
			return False
		else:
			return True
	elif message[0] == 'WHATSAT':	
		if message[1] not in client_position:
			return False
		elif not (isfloat(message[2])) or float(message[2]) <= 0 or float(message[2]) > 50000:
			return False
		elif not (message[3].isdigit()) or int(message[3]) > 20 or int(message[3]) < 0:
			return False
		else:
			return True
	else:
		return True



class Server:
	def __init__(self, name, ip = '127.0.0.1'):
	    self.name = name
	    self.port = port[name]
	    self.ip = ip

	async def handle_requests(self, reader, writer):
		"""
		on server side
		"""
		data = await reader.read()
		msg = data.decode()
		message = msg.split()

		if not validate(message):
			addr = writer.get_extra_info('peername')
			f.write("Received {} from {} {}\n".format(msg, *addr))
			f.flush()

			f.write("Send: {} back to {} {}\n".format(sendback_message,*addr))
			f.flush()
			writer.write(sendback_message.encode())
			await writer.drain()

			f.write("close the client socket with {} {}\n".format(*addr))
			f.flush()
			writer.close()

		else:
			if message[0] == 'IAMAT':
				t = message[3]
			elif message[0] == 'WHATSAT':
				t = None
			else:
				t = message[4]

			if t is None or t not in timestamp:
				if message[0] == 'IAMAT':
					sendback_message = await self.handle_IAMAT(message)
				elif message[0] == 'WHATSAT':
					sendback_message = await self.handle_WHATSAT(message)	
				else:
					sendback_message = await self.handle_FLOOD(message)

				addr = writer.get_extra_info('peername')
				f.write("Received {} from {} {}\n".format(msg, *addr))
				f.flush()

				f.write("Send: {} back to {} {}\n".format(sendback_message,*addr))
				f.flush()
				writer.write(sendback_message.encode())
				await writer.drain()

				f.write("close the client socket with {} {}\n".format(*addr))
				f.flush()
				writer.close()
			else:
				writer.close()

	async def handle_IAMAT(self,message):
		res = []
		res += ['AT',self.name]
		timediff = '%.9f' % (time.time() - float(message[3]))
		if float(timediff) > 0:
			timediff = '+' + timediff
		else:
			timediff = '-' + timediff

		res.append(timediff)
		res += message[1:]

		client_position[message[1]] = message[2]
		client_timediff[message[1]] = timediff
		client_time[message[1]] = message[3]
		first_server[message[1]] = self.name
		timestamp.add(message[3])

		for name in neighbor[self.name]:
			try:
				reader, writer = await asyncio.open_connection(host='127.0.0.1', port=port[name])
				reslist = ['FLOOD',message[1],message[2],timediff,message[3],self.name]

				propagate = ' '.join(reslist)
				writer.write(propagate.encode())
				await writer.drain()
				writer.close()
				f.write("Server on port " + name + " is running\n")
			except:
				f.write("Server on port " + name + " is down\n")


		return ' '.join(res)

	async def handle_WHATSAT(self,message):
		client_name = message[1]
		latitude,longitude = findLocation(client_position[client_name])
		loc = "{0},{1}".format(latitude,longitude)
		rad = int(message[2]) * 1000
		response = None
		async with ClientSession() as session:

			url = '{}/json?location={}&radius={}&key={}'.format(base_url,loc, rad, API_key)
			async with session.get(url) as resp:
				response = await resp.json()
		if len(response["results"]) > int(message[3]):
			response["results"] = response["results"][:int(message[3])]

		response = json.dumps(response, indent=3)
		reslist = ['AT',first_server[client_name],client_timediff[client_name],client_name,client_position[client_name],client_time[client_name]]
		response = ' '.join(reslist) + '\n' + response + '\n\n'

		return response

	async def handle_FLOOD(self,message):
		client_name = message[1]
		client_position[client_name] = message[2]
		client_timediff[client_name] = message[3]
		client_time[client_name] = message[4]
		first_server[client_name] = message[5]
		timestamp.add(message[4])

		for name in neighbor[self.name]:
			try:
				reader, writer = await asyncio.open_connection(host='127.0.0.1', port=port[name])
				propagate = ' '.join(message)
				writer.write(propagate.encode())
				await writer.drain()
				writer.close()
				f.write("Server on port " + name + " is running\n")
			except:
				f.write("Server on port " + name + " is down\n")			


		return ' '.join(message)



	async def run_forever(self):
		server = await asyncio.start_server(self.handle_requests, self.ip, self.port)

		print(f'serving on {server.sockets[0].getsockname()}')
		f.write(f'serving on {server.sockets[0].getsockname()}\n')
		f.flush()

		async with server:
		    await server.serve_forever()

		server.close()
		f.close()


def main():
	if len(sys.argv) != 2:
		print("Bad Argument")
	elif sys.argv[1] not in port:
		print("Bad server name")
	else:
		server_name = sys.argv[1]
		global f
		f = open('{}.log'.format(server_name),'w+')

		server = Server(name = server_name)
		try:
		    asyncio.run(server.run_forever())
		except KeyboardInterrupt:
		    pass


if __name__ == '__main__':
	main()