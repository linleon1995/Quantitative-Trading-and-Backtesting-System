# from datetime import datetime
# import pytest

# from src.create_backtest_database import ArcticDBOperator
# from tests.utils import generate_random_data


# @pytest.fixture
# def mock_data():
#     mock_data, start_time, end_time = generate_random_data(5)
#     return {'data': mock_data, 'start_time': start_time, 'end_time': end_time}


# @pytest.fixture
# def mock_db_operator(mock_data):
#     db_operator = ArcticDBOperator(url="lmdb://arctic_database", lib_name='test')
#     db_operator.write(data_name='BTCUSDT', data=mock_data['data'])
#     return db_operator


# def test_init(mock_db_operator):
#     assert mock_db_operator is not None
#     assert isinstance(mock_db_operator, ArcticDBOperator)


# # def test_write_data(mock_db_operator, mock_data):
# #     mock_db_operator.write(data_name='BTCUSDT', data=mock_data['data'])


# def test_read_non_exist_data(mock_db_operator, mock_data):
#     pass
#     # mock_db_operator.read(data_name='BTCUSDT', start)

# def test_read_exist_data(mock_db_operator, mock_data):
#     read_data = mock_db_operator.read(data_name='BTCUSDT', start_time=mock_data['start_time'], end_time=mock_data['end_time'])
#     assert read_data == mock_data['data']