# coding=utf-8

# ------------------------------------------------------------------------------------------------------

# TDA596 - Lab 1
# server/server.py
# Input: Node_ID total_number_of_ID

# Students:
# - Edoardo Puggioni
# - Jean-Nicolas Winter

# ------------------------------------------------------------------------------------------------------

import traceback
import sys
import time
import json
import argparse
from threading import Thread

from bottle import Bottle, run, request, template
import requests

# ------------------------------------------------------------------------------------------------------

try:
    app = Bottle()

    first = True

    # Dictionary to store all entries of the blackboard.
    board = {}

    # Logical clock
    clock = 0

    # mod_queue is a dictionary used to store a modification propagation that arrives to a node before the entry
    # to modify. In this way, when the entry is finally propagated, we can modify it accordingly.
    mod_queue = {}

    # del_queue works in the same way as mod_queue but for deleting entries.
    del_queue = {}

    # The following function will check the mod_queue dictionary and will apply the modifications contained.
    def check_mod_queue():
        global mod_queue
        for key in mod_queue:
            if key in board:
                modify_element_in_store(key, mod_queue[key])
                del mod_queue[key]
        return

    # The following function will check the del_queue dictionary and will apply the deletes contained.
    def check_del_queue():
        for key in del_queue:
            if key in board:
                delete_element_from_store(key)
                del del_queue[key]
        return

    # This function will be passed to the sorted function as a parameter, in order to have a custom sorting of the
    # board dictionary: first we sort using the clock, then using the id to break ties.
    def custom_sort(d):

        key = str(d[0])

        [ts, id] = key.split('.')

        return int(ts), int(id)

    # ------------------------------------------------------------------------------------------------------
    # BOARD FUNCTIONS
    # ------------------------------------------------------------------------------------------------------

    def add_new_element_to_store(entry_sequence, element, is_propagated_call=False):

        global board, node_id
        success = False

        try:
            # Simply add new element to the dictionary using entry_sequence as index.
            board[entry_sequence] = element
            success = True

        except Exception as e:
            print e

        return success

    def modify_element_in_store(entry_sequence, modified_element, is_propagated_call=False):

        global board, node_id, mod_queue
        success = False

        try:
            # Modify dictionary element using entry_sequence as index.
            board[entry_sequence] = modified_element
            success = True

        except Exception as e:
            print e

        return success

    def delete_element_from_store(entry_sequence, is_propagated_call=False):

        global board, node_id, del_queue
        success = False

        try:
            # Delete dictionary element using entry_sequence as index.
            del board[entry_sequence]
            success = True

        except Exception as e:
            print e

        return success

    # ------------------------------------------------------------------------------------------------------
    # DISTRIBUTED COMMUNICATIONS FUNCTIONS
    # ------------------------------------------------------------------------------------------------------

    def contact_vessel(vessel_ip, path, payload=None, req='POST'):

        # Try to contact another server (vessel) through a POST or GET, once
        success = False
        try:
            if 'POST' in req:
                res = requests.post('http://{}{}'.format(vessel_ip, path), data=payload)
            elif 'GET' in req:
                res = requests.get('http://{}{}'.format(vessel_ip, path))
            else:
                print 'Non implemented feature!'
            # result is in res.text or res.json()
            print(res.text)
            if res.status_code == 200:
                success = True
        except Exception as e:
            print e
        return success

    def propagate_to_vessels(path, payload=None, req='POST'):
        global vessel_list, node_id

        for vessel_id, vessel_ip in vessel_list.items():
            if int(vessel_id) != node_id:  # don't propagate to yourself
                success = contact_vessel(vessel_ip, path, payload, req)
                if not success:
                    print "\n\nCould not contact vessel {}\n\n".format(vessel_id)

    # In our optional task, we want to propagate the dictionary to all the node except one,
    # the one which is the connection between the two pools of nodes.
    def propagate_to_vessels_without(new_node_id, path, payload=None, req='POST'):
        global vessel_list, node_id

        for vessel_id, vessel_ip in vessel_list.items():
            if int(vessel_id) != node_id or str(new_node_id) != str(vessel_id):  # don't propagate to yourself
                success = contact_vessel(vessel_ip, path, payload, req)
                if not success:
                    print "\n\nCould not contact vessel {}\n\n".format(vessel_id)

    # ------------------------------------------------------------------------------------------------------
    # ROUTES
    # ------------------------------------------------------------------------------------------------------
    # a single example (index) should be done for get, and one for post
    # ------------------------------------------------------------------------------------------------------

    @app.route('/')
    def index():
        global board, node_id

        # Every time the page is refreshed we check the queues to apply modifications or deletes.
        check_mod_queue()
        check_del_queue()

        # In the sorted() function we pass custom_sort as parameter to have a custom sorting of the board dictionary.
        return template('server/index.tpl', board_title='Vessel {}'.format(node_id),
                        board_dict=sorted(board.iteritems(), key=custom_sort), members_name_string='YOUR NAME')

    @app.get('/board')
    def get_board():
        global board, node_id

        # Every time the page is refreshed we check the queues to apply modifications or deletes.
        check_mod_queue()
        check_del_queue()

        # In the sorted() function we pass custom_sort as parameter to have a custom sorting of the board dictionary.
        return template('server/boardcontents_template.tpl', board_title='Vessel {}'.format(node_id),
                        board_dict=sorted(board.iteritems(), key=custom_sort))

    # ------------------------------------------------------------------------------------------------------

    @app.post('/board')
    def client_add_received():

        # Adds a new element to the board.
        # Called directly when a user is doing a POST request on /board.

        global board, node_id, id, clock, vessel_list, node_id, first

        # Printing in a file for measurements.
        # if first:
        #     filename = str(node_id) + "file.txt"
        #     file = open(filename, "w")
        #     file.write(str(time.time()) + "\n\n")
        #     file.close()
        #     first = False

        try:

            new_entry = request.forms.get('entry')

            # Increment clock before event
            clock += 1

            # Build entry ID which will serve as a key for the board dictionary.
            element_id = str(clock) + '.' + str(node_id)

            # We add new element to dictionary using element_id as entry sequence.
            add_new_element_to_store(element_id, new_entry)

            # Increment again before propagation.
            clock += 1

            # Path to propagate, key word "add". Also timestamp and element_id of the new entry.
            path = "/propagate/add/" + str(clock) + '/' + str(element_id)

            # Start thread so the server doesn't make the client wait.
            thread = Thread(target=propagate_to_vessels, args=(path, new_entry,))
            thread.deamon = True
            thread.start()
            return True

        except Exception as e:
            print e

        return False

    @app.post('/board/<element_id>/')
    def client_action_received(element_id):

        global clock

        # Modify or delete an element in the board
        # Called directly when a user is doing a POST request on /board/<element_id:int>/

        # Retrieving the ID of the action, which can be either 0 or 1.
        # 0 is received when the user clicks on "modify".
        # 1 is received when the user clicks on "delete".
        delete = request.forms.get('delete')

        element_id = str(element_id)

        if delete == "0":
            # User wants to modify entry with ID given by element_id.

            new_entry = request.forms.get('entry')

            # Increment clock before event
            clock += 1

            modify_element_in_store(element_id, new_entry)

            # Increment again before propagation.
            clock += 1

            # Build path to propagate using keyword "mod" which stands for "modify".
            # Send the new timestamp, but don't change the message ID, send the original.
            path = "/propagate/mod/" + str(clock) + '/' + str(element_id)

            thread = Thread(target=propagate_to_vessels, args=(path, new_entry,))
            thread.deamon = True
            thread.start()

        elif delete == "1":
            # User wants to delete entry with ID given by element_id.

            # Increment clock before event
            clock += 1

            delete_element_from_store(entry_sequence=element_id)

            # Increment again before propagation.
            clock += 1

            # Build path to propagate using keyword "del" which stands for "delete".
            # Send the new timestamp, but don't change the message ID, send the original.
            path = "/propagate/del/" + str(clock) + '/' + str(element_id)

            thread = Thread(target=propagate_to_vessels, args=(path, "nothing",))
            thread.deamon = True
            thread.start()

        pass

    @app.post('/propagate/<action>/<msg_timestamp>/<msg_id>')
    def propagation_received(action, msg_timestamp, msg_id):

        global clock, node_id, mod_queue, del_queue

        # Propagate action. An action is distinguished using one of the three keywords "add", "mod" and "del", which
        # stand for add, modify and delete respectively. After identifying the action, we identify the entry to
        # add/modify/delete by using the variable element_id, and also in the case of add and modify, the new entry can
        # be retrieved from the body of the POST request.

        # As explained in the slides and in the book, the logical clocks algorithms dictates that we should update the
        # local logical clock as follows, when receiving a message.
        if int(msg_timestamp) > clock:
            clock = int(msg_timestamp)

        clock += 1

        if action == "add":

            # We retrieve the new entry from the body of the POST request.
            entry = request.body.read()
            add_new_element_to_store(msg_id, entry)

            # Printing in a file for measurements.
            # filename = str(node_id) + "file.txt"
            # file = open(filename, "a")
            # file.write(str(time.time()) + "\n\n")
            # file.close()

        if action == "mod":

            # We retrieve the new entry from the body of the POST request.
            entry = request.body.read()

            # To consider the case in which a propagation about a modification arrives but the element to be modified
            # is not been propagated yet, we keep a queue of element to modify: this queue will be checked every time
            # the board is requested for displaying in the web-app, and it will be emptied when needed.
            if msg_id not in board:
                mod_queue[msg_id] = entry
            else:
                modify_element_in_store(msg_id, entry)

        if action == "del":

            # As for modify propagation above, we use a queue also for elements to be deleted.
            if msg_id not in board:
                del_queue[msg_id] = 1
            else:
                delete_element_from_store(entry_sequence=msg_id)

        pass


    # ------------------------------------------------------------------------------------------------------
    # Optional task
    # ------------------------------------------------------------------------------------------------------

    # We are going to do 2 pools of servers, each pool independant from each others.
    # To do so, we are customazing the vessel_list of each other, the first pool will have a vessel-list of
    # the vessels of the first pool, the same for the second pool.
    # To connect the two pool, we a creating a route to add one node to a all the nodes in the pool

    # The two pool of vessels are connected. They will then propagate all the data transmitted by the vessel from
    # the other pool, without sending him back the same messages
    # element_id : id of the element to add
    # node_id : vessel to not propagate the data (the one who already sent the elements
    # request.body.read() : value of the element to add
    @app.post('/addVessel/data/<element_id>/<node_id>')
    def propagateData(element_id, node_id):
        global vessel_list, clock

        #make the clock consistent

        clock += 1

        #add the entry to the dictionary
        new_entry = request.body.read()
        add_new_element_to_store(element_id, new_entry)

        clock += 1


        path = "/propagate/add/" + str(clock) + '/' + str(element_id)

        # Start thread so the server doesn't make the others wait. We propagate to all the nodes in
        # our list without the one giving us the entries, the "node_id"
        thread = Thread(target=propagate_to_vessels_without, args=(node_id, path, new_entry,))
        thread.deamon = True
        thread.start()

        pass


    # Adding one server to the vessel-list of all the nodes in the pool
    # then contact the new server to propagate the data from this first pool
    # new_node_id : id of the new node to add
    # new_node_ip . ip of the new node to add
    # propagate : "0" if propagate to the other, "1" if we are the others
    @app.post('/addVessel/<new_node_id>/<new_node_ip>/<propagate>')
    def addNewVessel(new_node_id, new_node_ip, propagate):
        global vessel_list, node_id

        # we are the first node, we propagate to all the vessel in the pool
        # a server to add, specify propagate : 1 to tell them not to propagate again
        if str(propagate) == "0":
            path = "/addVessel/" + str(new_node_id) + '/' + str(new_node_ip) + "/1"

            # Start thread so the server doesn't make the client wait.
            thread = Thread(target=propagate_to_vessels, args=(path,))
            thread.deamon = True
            thread.start()

        # add the server to the vessel_list
        vessel_list[str(new_node_id)] = new_node_ip


        # contact the new server to give him the data from this pool
        for id, value in board.iteritems():
            path = "/addVessel/data/" + str(id) + "/" + str(node_id)
            # Start thread so the server doesn't make the client wait.
            thread = Thread(target=contact_vessel, args=(new_node_ip, path, value,))
            thread.deamon = True
            thread.start()
        pass

    # Delete one server to the vessel-list of all the nodes in the pool
    # new_node_id : id of the new node to add
    # propagate : "0" if propagate to the other, "1" if we are the others
    @app.post('/deleteVessel/<new_node_id>/<propagate>')
    def deleteVessel(new_node_id, new_node_ip, propagate):
        global vessel_list, node_id

        # we are the first node, we propagate to all the vessel in the pool
        # a server to add, specify propagate : 1 to tell them not to propagate again
        if str(propagate) == "0":
            path = "/deleteVessel/" + str(new_node_id) + '/1'

            # Start thread so the server doesn't make the client wait.
            thread = Thread(target=propagate_to_vessels, args=(path,))
            thread.deamon = True
            thread.start()

        # add the server to the vessel_list
        vessel_list[str(new_node_id)] = new_node_ip

        pass


    # ------------------------------------------------------------------------------------------------------
    # EXECUTION
    # ------------------------------------------------------------------------------------------------------

    # Execute the code

    def main():
        global vessel_list, node_id, app

        port = 80
        parser = argparse.ArgumentParser(description='Your own implementation of the distributed blackboard')
        parser.add_argument('--id', nargs='?', dest='nid', default=1, type=int, help='This server ID')
        parser.add_argument('--vessels', nargs='?', dest='nbv', default=1, type=int,
                            help='The total number of vessels present in the system')
        args = parser.parse_args()
        node_id = args.nid
        vessel_list = dict()
        # We need to write the other vessels IP, based on the knowledge of their number
        for i in range(1, args.nbv+1):
            # if str(node_id) <= str(5) and i <= 5: #first pool of 5 vessels
            #     vessel_list[str(i)] = '10.1.0.{}'.format(str(i))
            # elif str(node_id) > str(5) and i > 5: #second pool of the vessels
            #     vessel_list[str(i)] = '10.1.0.{}'.format(str(i))

            vessel_list[str(i)] = '10.1.0.{}'.format(str(i))

        try:
            run(app, host=vessel_list[str(node_id)], port=port)
        except Exception as e:
            print e

    # ------------------------------------------------------------------------------------------------------

    if __name__ == '__main__':
        main()

except Exception as e:
    traceback.print_exc()
    while True:
        time.sleep(60.)
