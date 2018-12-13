for i in {1..40}; do

	curl -d "entry=t$i-1" -X 'POST' "http://10.1.0.1/board" &
	curl -d "entry=t$i-2" -X 'POST' "http://10.1.0.2/board" &
	curl -d "entry=t$i-3" -X 'POST' "http://10.1.0.3/board" &
	curl -d "entry=t$i-4" -X 'POST' "http://10.1.0.4/board" &
	curl -d "entry=t$i-4" -X 'POST' "http://10.1.0.5/board" &
	curl -d "entry=t$i-4" -X 'POST' "http://10.1.0.6/board" &
	curl -d "entry=t$i-4" -X 'POST' "http://10.1.0.7/board" &
	curl -d "entry=t$i-4" -X 'POST' "http://10.1.0.8/board" &

done
