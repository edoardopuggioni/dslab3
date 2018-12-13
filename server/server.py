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

    # Dictionary to store all entries of the blackboard.
    board = {}

    # Logical clock
    clock = 0

    mod_queue = {}

    del_queue = {}

    # Dictionary similar to board, used only to display the board on the web-app, to hide the internal IDs of the
    # entries, showing instead simple sequence numbers 1, 2, 3, and so on.
    board_display = {}

    # Dictionary to map sequnce numbers to internal IDs.
    seq_to_id = {}

    def check_mod_queue():
        global mod_queue
        for key in mod_queue:
            if key in board:
                modify_element_in_store(key, mod_queue[key])
                del mod_queue[key]
        return

    def check_del_queue():
        for key in del_queue:
            if key in board:
                delete_element_from_store(key)
                del del_queue[key]
        return

    def update_board_display():

        global board, board_display, seq_to_id

        board_display = {}
        seq_to_id = {}
        i = 1
        for key, value in sorted(board.iteritems(), key=custom_sort):
            board_display[i] = value
            seq_to_id[i] = key
            i += 1

        return

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

    # ------------------------------------------------------------------------------------------------------
    # ROUTES
    # ------------------------------------------------------------------------------------------------------
    # a single example (index) should be done for get, and one for post
    # ------------------------------------------------------------------------------------------------------

    @app.route('/')
    def index():
        global board, node_id, board_display, seq_to_id

        check_mod_queue()
        check_del_queue()

         # update_board_display()

        return template('server/index.tpl', board_title='Vessel {}'.format(node_id),
                        board_dict=sorted(board.iteritems(), key=custom_sort), members_name_string='YOUR NAME')

    @app.get('/board')
    def get_board():
        global board, node_id, board_display, seq_to_id

        check_mod_queue()
        check_del_queue()

        # update_board_display()

        return template('server/boardcontents_template.tpl', board_title='Vessel {}'.format(node_id),
                        board_dict=sorted(board.iteritems(), key=custom_sort))

    # ------------------------------------------------------------------------------------------------------

    @app.post('/board')
    def client_add_received():

        # Adds a new element to the board.
        # Called directly when a user is doing a POST request on /board.

        global board, node_id, id, clock, vessel_list, node_id

        try:

            new_entry = request.forms.get('entry')

            # Increment clock before event
            clock += 1

            # Build entry ID which will serve as a key for the board dictionary.
            element_id = str(clock) + '.' + str(node_id)

            # We add new element to dictionary using element_id as entry sequence.
            add_new_element_to_store(element_id, new_entry)
            
            # It's not clear from the slides or the book if in the logical clock algorithm we have to increment the 
            # clock value again here before propagation. We will try to do it and see what happens.
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

        # The following three lines can be ignored: idea that has been discarded.
        # In the web-app we display a sequence number instead of the real ID of the element, so now we have to
        # retrieve the ID using the dictionary we built for this particular mapping.
        # element_id = seq_to_id[int(element_seq)]

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

        if int(msg_timestamp) > clock:
            clock = int(msg_timestamp)

        clock += 1

        if action == "add":

            # We retrieve the new entry from the body of the POST request.
            entry = request.body.read()
            add_new_element_to_store(msg_id, entry)

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
        for i in range(1, args.nbv):
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
