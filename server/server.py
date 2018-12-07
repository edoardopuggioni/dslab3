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

    def check_mod_queue():
        global mod_queue
        for key, value in mod_queue:
            if key in board:
                modify_element_in_store(key, value)
                del mod_queue[key]

    def check_del_queue():
        for key in del_queue:
            if key in board:
                delete_element_from_store(key)
                del del_queue[key]

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
        global board, node_id, mod_queue

        check_mod_queue()
        check_mod_queue()

        return template('server/index.tpl', board_title='Vessel {}'.format(node_id),
                        board_dict=sorted(board.iteritems()), members_name_string='YOUR NAME')

    @app.get('/board')
    def get_board():
        global board, node_id

        check_mod_queue()
        check_mod_queue()

        # The following code to build board_display was meant for having a "good looking" way of displaying the IDs in
        # the web-application (IDs going 0, 1, 2, etc.) but we need to keep the "ugly" IDs to maintain them unique.
        # board_display = {}
        # i = 0
        # for key in sorted(board.iteritems()):
        #     board_display[str(i)] = board[key]
        #     i += 1

        return template('server/boardcontents_template.tpl', board_title='Vessel {}'.format(node_id),
                        board_dict=sorted(board.iteritems()))

    # ------------------------------------------------------------------------------------------------------

    @app.post('/board')
    def client_add_received():

        # Adds a new element to the board
        # Called directly when a user is doing a POST request on /board

        global board, node_id, id, clock, vessel_list, node_id

        try:

            new_entry = request.forms.get('entry')

            # Increment clock before event
            clock += 1

            # Build entry ID which will serve as a key for the board dictionary.
            element_id = str(clock) + str(node_id)

            # We add new element to dictionary using id as entry sequence.
            add_new_element_to_store(str(element_id), new_entry)

            # Build path to propagate, using key word "add" and id as element_id.
            path = "/propagate/add/" + str(clock) + '/' + str(element_id)

            # Start thread so the server doesn't make the client wait.
            thread = Thread(target=propagate_to_vessels, args=(path, new_entry,))
            thread.deamon = True
            thread.start()
            return True

        except Exception as e:
            print e

        return False

    @app.post('/board/<element_id:int>/')
    def client_action_received(element_id):

        global clock

        # Modify or delete an element in the board
        # Called directly when a user is doing a POST request on /board/<element_id:int>/

        # Retrieving the ID of the action, which can be either 0 or 1.
        # 0 is received when the user clicks on "modify".
        # 1 is received when the user clicks on "delete".
        delete = request.forms.get('delete')

        if delete == "0":
            # User wants to modify entry with ID given by element_id.

            new_entry = request.forms.get('entry')

            # Increment clock before event
            clock += 1

            modify_element_in_store(str(element_id), new_entry)

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

            delete_element_from_store(entry_sequence=str(element_id))

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

            if msg_id not in board:
                mod_queue[msg_id] = entry
            else:
                modify_element_in_store(msg_id, entry)

        if action == "del":

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
