from datetime import datetime, timedelta

from src.strategies.base_strategy import TestStateMachine


def test_state_machine():
    state_machine = TestStateMachine(
        symbol='BTCUSDT',
        maxlen=1440,
        ma_range_list=[7, 25, 99],
        stable_length=50
    )
    assert state_machine.current_state.id == 's0'
    assert isinstance(state_machine, TestStateMachine)

    t1 = datetime.now()
    t = t1
    for _ in range(100):
        t += timedelta(minutes=1)
        state_machine.receive(price=100, timestamp=t)
    assert state_machine.current_state.id == 's1'

    # print(state_machine.current_state.id)
    state_machine.receive(price=150, timestamp=t2)
    # print(state_machine.current_state.id)
    state_machine.receive(price=150, timestamp=t2)
    # print(state_machine.current_state.id)
    state_machine.receive(price=150, timestamp=t2)
    # print(state_machine.current_state.id)
    assert state_machine.current_state.id == 's0'


    
    

