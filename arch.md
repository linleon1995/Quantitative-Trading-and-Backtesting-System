graph TD
    %% [1] 資料與狀態層
    subgraph Data_Layer ["Data_State_Input_Layer"]
        direction TB
        Ex_WS["Exchange_WS"] --> State_Mgr["State_Manager"]
        State_Mgr -->|Inject_Price| Performance_Mgr
        State_Mgr --> Calc_Stats["Indicator_Calculator"]
    end

    %% [2] 策略決策層
    subgraph Strategy_Layer ["Strategy_Brain_Layer"]
        Core_Logic["Core_Strategy_Logic"]
    end

    %% [3] 協調與風控層
    subgraph Portfolio_Layer ["Portfolio_Risk_Layer"]
        Coord_Mgr["Portfolio_Coordinator"]
        Risk_Ctrl["Risk_Manager"]
        Performance_Mgr -->|Inject_Equity_Curve| Coord_Mgr
    end

    %% [4] 執行與訂單管理層
    subgraph Execution_Layer ["Execution_OMS_Layer"]
        Exe_Engine["Execution_Engine"]
        On_Flight_Mgr["Pending_Order_Manager"]
    end

    %% [5] 績效與會計層 (新元件)
    subgraph Accounting_Layer ["Performance_Accounting_Layer"]
        direction TB
        Performance_Mgr["Performance_Analyzer"]
        Trade_Logger["Trade_History_Database"]
        Performance_Mgr --> Trade_Logger
    end

    %% [6] 介面層
    subgraph Interface_Layer ["Exchange_Interface_Layer"]
        Ex_Adapter["Exchange_Adapter_Trader"]
    end

    %% 資料流
    Calc_Stats --> Core_Logic
    Core_Logic --> Coord_Mgr
    Coord_Mgr --> Risk_Ctrl
    Risk_Ctrl --> Exe_Engine
    Exe_Engine <--> On_Flight_Mgr
    Exe_Engine --> Ex_Adapter
    
    %% 確定性回報流
    Ex_Adapter -->|1.Order_Fill| Performance_Mgr
    Ex_Adapter -->|2.Balance_Update| Performance_Mgr
    Ex_Adapter -->|3.Order_Update| On_Flight_Mgr

    %% 風格
    classDef performance fill:#bbf,stroke:#333,stroke-width:2px;
    class Performance_Mgr,Trade_Logger performance;

    %% 風格定義
    classDef data fill:#f9f,stroke:#333,stroke-width:1px;
    classDef strategy fill:#ccf,stroke:#333,stroke-width:2px,stroke-dasharray: 5 5;
    classDef portfolio fill:#ff9,stroke:#333,stroke-width:2px;
    classDef execution fill:#f96,stroke:#333,stroke-width:2px;
    classDef interface fill:#ddd,stroke:#333,stroke-width:1px;

    class Ex_WS,Ex_REST,State_Mgr,Calc_Stats data;
    class Core_Logic,Ideal_Weights strategy;
    class Coord_Mgr,Risk_Ctrl,Alloc_Pos portfolio;
    class Exe_Engine,On_Flight_Mgr,Local_Inv,Order_Cmd execution;
    class Ex_Adapter interface;