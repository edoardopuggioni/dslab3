for i in {1..9}; do
if [i%2 -eq 0]
then
	curl -d "entry=t$i" -X 'POST' "http://10.1.0.$i/board" &
else
	j = -$i
	curl -d "entry=t$j" -X 'POST' "http://10.1.0.$i/board/<element_id:int>/" &
done


# I wanted to test the following:
#
#	add id1, entryA
#	mod id1, entryB
#	add id2, entryC
#	mod id2, entryD
#
# and so on, to test the edge case in which a mod propagation arrives
# before the propagation of new entry that has to be modified. However
# I cannot do it because it's impossible to know the ID of the next 
# new entry in advance from this bash script: I miss element_id.