import queue
import threading
from rprint import print


## wrapper class for a queue of packets
class Interface:
    ## @param maxsize - the maximum size of the queue storing packets
    def __init__(self, maxsize=0):
        self.in_queue = queue.Queue(maxsize)
        self.out_queue = queue.Queue(maxsize)
    
    ##get packet from the queue interface
    # @param in_or_out - use 'in' or 'out' interface
    def get(self, in_or_out):
        try:
            if in_or_out == 'in':
                pkt_S = self.in_queue.get(False)
                # if pkt_S is not None:
                #     print('getting packet from the IN queue')
                return pkt_S
            else:
                pkt_S = self.out_queue.get(False)
                # if pkt_S is not None:
                #     print('getting packet from the OUT queue')
                return pkt_S
        except queue.Empty:
            return None
        
    ##put the packet into the interface queue
    # @param pkt - Packet to be inserted into the queue
    # @param in_or_out - use 'in' or 'out' interface
    # @param block - if True, block until room in queue, if False may throw queue.Full exception
    def put(self, pkt, in_or_out, block=False):
        if in_or_out == 'out':
            # print('putting packet in the OUT queue')
            self.out_queue.put(pkt, block)
        else:
            # print('putting packet in the IN queue')
            self.in_queue.put(pkt, block)
            
        
## Implements a network layer packet.
class NetworkPacket:
    ## packet encoding lengths 
    dst_S_length = 5
    prot_S_length = 1
    
    ##@param dst: address of the destination host
    # @param data_S: packet payload
    # @param prot_S: upper layer protocol for the packet (data, or control)
    def __init__(self, dst, prot_S, data_S):
        self.dst = dst
        self.data_S = data_S
        self.prot_S = prot_S
        
    ## called when printing the object
    def __str__(self):
        return self.to_byte_S()
        
    ## convert packet to a byte string for transmission over links
    def to_byte_S(self):
        byte_S = str(self.dst).zfill(self.dst_S_length)
        if self.prot_S == 'data':
            byte_S += '1'
        elif self.prot_S == 'control':
            byte_S += '2'
        else:
            raise('%s: unknown prot_S option: %s' %(self, self.prot_S))
        byte_S += self.data_S
        return byte_S
    
    ## extract a packet object from a byte string
    # @param byte_S: byte string representation of the packet
    @classmethod
    def from_byte_S(self, byte_S):
        dst = byte_S[0 : NetworkPacket.dst_S_length].strip('0')
        prot_S = byte_S[NetworkPacket.dst_S_length : NetworkPacket.dst_S_length + NetworkPacket.prot_S_length]
        if prot_S == '1':
            prot_S = 'data'
        elif prot_S == '2':
            prot_S = 'control'
        else:
            raise('%s: unknown prot_S field: %s' %(self, prot_S))
        data_S = byte_S[NetworkPacket.dst_S_length + NetworkPacket.prot_S_length : ]        
        return self(dst, prot_S, data_S)
    

    

## Implements a network host for receiving and transmitting data
class Host:
    
    ##@param addr: address of this node represented as an integer
    def __init__(self, addr):
        self.addr = addr
        self.intf_L = [Interface()]
        self.stop = False #for thread termination
    
    ## called when printing the object
    def __str__(self):
        return self.addr
       
    ## create a packet and enqueue for transmission
    # @param dst: destination address for the packet
    # @param data_S: data being transmitted to the network layer
    def udt_send(self, dst, data_S):
        p = NetworkPacket(dst, 'data', data_S)
        print('%s: sending packet "%s"' % (self, p))
        self.intf_L[0].put(p.to_byte_S(), 'out') #send packets always enqueued successfully
        
    ## receive packet from the network layer
    def udt_receive(self):
        pkt_S = self.intf_L[0].get('in')
        if pkt_S is not None:
            print('%s: received packet "%s"' % (self, pkt_S))
       
    ## thread target for the host to keep receiving data
    def run(self):
        print (threading.currentThread().getName() + ': Starting')
        while True:
            #receive data arriving to the in interface
            self.udt_receive()
            #terminate
            if(self.stop):
                print (threading.currentThread().getName() + ': Ending')
                return
        


## Implements a multi-interface router
class Router:
    
    ##@param name: friendly router name for debugging
    # @param cost_D: cost table to neighbors {neighbor: {interface: cost}}
    # @param max_queue_size: max queue length (passed to Interface)
    def __init__(self, name, cost_D, max_queue_size):
        self.stop = False #for thread termination
        self.name = name
        #create a list of interfaces
        self.intf_L = [Interface(max_queue_size) for _ in range(len(cost_D))]
        #save neighbors and interfeces on which we connect to them
        self.cost_D = cost_D    # {neighbor: {interface: cost}}
        self.table = RoutingTable(cost_D, name)
        self.rt_tbl_D = {}      # {destination: {router: cost}}
        print('%s: Initialized routing table' % self)
        self.print_routes2()
    
        
    ## Print routing table
    def print_routes(self):
        #TODO: print the routes as a two dimensional table
        self.print_routes2()

    def print_routes2(self):
        retS = '\n'
        retS += self.name
        retS += ":\n      "
        for item in self.table.getDests():
            retS += str(item) + "    "
        retS += "\n"
        for r in self.table.getRouters():
            retS += str(r)
            for d in self.table.getDests():
                c = self.table.getCostOf(d, r)
                if((c < 0) or (c > 9)):
                    retS += "    "
                else:
                    retS += "     "
                retS += str(c)
                
            retS += "\n"
        
        print(retS)


    ## called when printing the object
    def __str__(self):
        return self.name


    ## look through the content of incoming interfaces and 
    # process data and control packets
    def process_queues(self):
        for i in range(len(self.intf_L)):
            pkt_S = None
            #get packet from interface i
            pkt_S = self.intf_L[i].get('in')
            #if packet exists make a forwarding decision
            if pkt_S is not None:
                p = NetworkPacket.from_byte_S(pkt_S) #parse a packet out
                if p.prot_S == 'data':
                    self.forward_packet(p,i)
                elif p.prot_S == 'control':
                    self.update_routes(p, i)
                else:
                    raise Exception('%s: Unknown packet type in packet %s' % (self, p))
            

    ## forward the packet according to the routing table
    #  @param p Packet to forward
    #  @param i Incoming interface number for packet p
    def forward_packet(self, p, i):
        try:
            # TODO: Here you will need to implement a lookup into the 
            # forwarding table to find the appropriate outgoing interface
            # for now we assume the outgoing interface is 1
            self.intf_L[1].put(p.to_byte_S(), 'out', True)
            print('%s: forwarding packet "%s" from interface %d to %d' % \
                (self, p, i, 1))
        except queue.Full:
            print('%s: packet "%s" lost on interface %d' % (self, p, i))
            pass


    ## send out route update
    # @param i Interface number on which to send out a routing update
    def send_routes(self, i):
        # TODO: Send out a routing table update
        #create a routing table update packet
        p = NetworkPacket(0, 'control', str(self.table))
        try:
            print('%s: sending routing update "%s" from interface %d' % (self, p, i))
            self.intf_L[i].put(p.to_byte_S(), 'out', True)
        except queue.Full:
            print('%s: packet "%s" lost on interface %d' % (self, p, i))
            pass


    ## forward the packet according to the routing table
    #  @param p Packet containing routing information
    def update_routes(self, p, i):
        #TODO: add logic to update the routing tables and
        # possibly send out routing updates
        boolean = self.table.updateTable(i, p.data_S)
        print('%s: Received routing update %s from interface %d' % (self, p, i))
        print(self.print_routes2())
        if(boolean == True):
            self.send_routes(i)

                
    ## thread target for the host to keep forwarding data
    def run(self):
        print (threading.currentThread().getName() + ': Starting')
        while True:
            self.process_queues()
            if self.stop:
                print (threading.currentThread().getName() + ': Ending')
                return


class RoutingTable:
    
    def __init__(self, cost_D, name):
        self.name = name
        self.costD = cost_D
        self.costDicts = {self.name: self.costD}
        self.reachable = []
        self.routers = []
        self.dests = []
        self.routers.append(self.name)
        self.dests.append(self.name)
        self.reachable.append(self.name)
        for key in cost_D:
            self.dests.append(key)
            self.reachable.append(key)
            if(key[0] == 'R'):
                self.routers.append(key)
                self.costDicts[key] = -1
##        print(self.costDicts)
##        print("self:")
##        print(self)
##        print()

    def bestPath(self, dest):
        return -1 #out interface 

    def getCostOf(self, dest, router):
        if(dest == router):
            return 0
        if(router in self.costDicts.keys()):
            costs = self.costDicts[router]
            minVal = None
            if(isinstance(costs, dict)):
                for key in costs:
                    #print("dest: " + str(dest) + "\tthis key: " + str(key))
                    if(key == dest):
                        intFaces = costs[key]
                        #print("this iFace: " + str(intFaces))
                        #print()
                        for intF in intFaces:
                            if(minVal == None):
                                minVal = intFaces[intF]
                            else:
                                minVal = intFaces[intF] if intFaces[intF] < minVal else minVal           
                return -1 if minVal == None else minVal #cost
            else: #do not yet know connections for this router
                return -1

        else:
            return (self.getCostOf(router, self.name) + self.getCostOf(dest, self.name))

    def getBestRoute(self, dest):
        return -1 #interface

    def getRouters(self):
        return self.routers

    def getDests(self):
        return self.dests

    def getCosts(self):
        return []

    def updateTable(self, intF_in, dataIn):
        changed = False
        thisDict = self.costDicts[self.name]
        r = None
        rIn = None
        for key in thisDict:
            if(r != None):
                break
            elif(key in thisDict.keys()):
                paths = thisDict[key]
                for intF in paths:
                    if(int(intF) == int(intF_in)):
                        r = key
                        #print("From: " + str(key))

        self.costDicts[r] = RoutingTable.fromStr(dataIn)

        rTable = self.costDicts[r]
        for key in rTable:
            if(key not in thisDict.keys()):
                if(key == self.name):
                    continue
                thisDict[key] = {intF_in: (int(self.getCostOf(r, self.name)) + int(self.getCostOf(key, r)))}
                self.costDicts[self.name] = thisDict
                self.dests.append(key)
                changed = True
            else:
                #print("here")
                #print(key)
                dv = self.DV(key)
                path = dv[0]
                cost = dv[1]
                #print(path)
                #print(cost)
                #print()
                #thisDict[
        #print(self.costDicts)   
        print(str(self.name) + " Table Updated")
        return changed

    def intF_Of(self, node):
        this = self.costDicts[self.name]
        #print("in ", end='')
        #print(self.name, end='')
        #print(" looking for: ", end='')
        #print(node)
        #print(this)
        if(node in this.keys()):
            i = 0
            key = None
            #print(this[node])
            while(key == None):
                if(i in this[node].keys()):
                    key = i
                    #print("intF of " + str(node) + ": " + str(i))
                    return i
                i += 1
        else:
            #print("FAILED")
            return -1

    def DV(self, dest):
        thisDict = self.costDicts[self.name]
        via = None
        cost = None
        for path in self.reachable:
            if(via == None):
                via = path
                
            if(path == dest):
                c = 0
                dv = self.getCostOf(dest, self.name)
            else:
                c = self.getCostOf(path, self.name)
                dv = self.getCostOf(dest, path)

            if(cost == None):
                cost = c + dv
                via = path
            elif((c + dv) < cost):
                cost = c + dv
                via = path
                
        return [via, cost] if ((via != None) and (cost != None)) else [-1, -1] #path and cost taken to dest
                

##    def DvNxt(self, name, dest):
##        thisDict = self.costDicts[name]
##        for path in self.reachable:
##            c = self.cost(self.name, path)
##            dv = 
##            cost =  +

    def __str__(self):
        return self.toStr()
    
    def toStr(self):
        retS = ''
        retS += str(self.name)
        retS += ';'
        this = self.costDicts[self.name]
        if(isinstance(this, int)):
            retS += "DNE"
            return retS
        for connection in this:
            if(isinstance(connection, int)):
                retS += "DNE"
                continue
            retS += str(connection) + ':'
            intF = this[connection]
            if(isinstance(intF, int)):
                retS += "DNE"
                continue
            for key in intF:
                retS += str(key) + ':' + str(intF[key]) + ';'
        return retS

    @classmethod
    def fromStr(self, s):
        dictionary = {}
        data = s
        name = ''
        i = 0
        char = data[0]
        while char != ';':
            name += char
            i += 1
            char = data[i]
        #print("name:")
       # print(name)
        data = data[i+1:]
        #print(data)
        data = data.split(';')
        for entry in data:
            if(len(entry) < 2):
                continue
            e = entry.split(':')
            #print(e)
            dest = e[0]
            intF = e[1]
            cost = e[2]
            dictionary[dest] = {int(intF):int(cost)}
        #print(dictionary)
        return dictionary #return other.costDicts[other.name] 
        
        

##class RoutingTable:
##    name = ''
##    dests = [] #network destinations (top)
##    costs = None #list of costs corresponting to this destination
##    known = [] #paths through known routers (column)
##    costD = None
##    
##    def __init__(self, cost_D, name):
##        self.name = ''
##        self.dests = []
##        self.costs = []
##        self.known = []
##        self.costD = None
##        self.costD = cost_D
##        self.name = name
##        self.known.append(self.name)
##        self.dests.append(self.name)
##        for key in self.costD:
##            self.dests.append(key)
##            if(isinstance(key, str)):
##                if(key[0] == 'R'):
##                    self.known.append(key)
##        self.costs = [[{0: -1} for g in range(len(self.dests))] for h in range(len(self.known))]
##        for i in range(len(self.known)):
##            for j in range(len(self.dest)):
##                d = self.dests[j]
##                r = self.known[i]
##                
##                
##
##        print("name: " + self.name)
##        print(self.costD)
##        print(self.dests)
##        print(self.costs)
##        print(self.known)
##
##    def getKnown(self):
##        return self.known
##
##    def getCosts(self):
##        return self.costs
##
##    def getDests(self):
##        return self.dests
##
##    def getCostOf(self, dest, router):
##        d = self.dests.index(dest)
##        r = self.known.index(router)
##        costs = self.costs[r][d]
##        minVal = None
##        for key in costs:
##            this = costs[key]
##            if(minVal == None):
##                minVal = this
##            if((this < minVal) and (this > -1)):
##                minVal = this
##        return minVal






        