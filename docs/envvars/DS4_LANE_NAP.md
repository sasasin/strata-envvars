# DS4_LANE_NAP

調査対象: Strata main の HEAD c62d5e3a15b40ea51c96aae9e8d36928965f53ab（2026-11-01 時点）。

## 役割

DeepSeek-V4.1 engine (strata-dsv41) の CPU lane service thread が要求待ちで休止するとき、Windows 高解像度 waitable timer を使うかを切り替えます。DS4_LANE_NAP=sleep のときはタイマーを使わず、sleep_for(20 us) に進みます。それ以外の値では高解像度タイマーの作成を試します。この変数は要求処理や CPU lane の計算内容を選ぶものではなく、アイドル待ちの方法だけを変えます。

## 値と判定

値の文字列全体を "sleep" と比較します。数値変換、trim、大文字小文字変換はありません。

| OS / 値 | 判定と処理 |
|---|---|
| Windows、未設定 | hires=true。高解像度 waitable timer の作成を試みる |
| Windows、値が厳密に sleep | hires=false。タイマーを作らず sleep_for(20 us) に進む |
| Windows、その他の設定値（空文字、0、Sleep を含む） | hires=true。高解像度 waitable timer の作成を試みる |
| Windows 以外 | この変数を読むコードはコンパイルされず、sleep_for(20 us) に進む |

## 有効になる条件

- CUDA または HIP backend で STRATA_BUILD_DSV41 を有効にして DeepSeek-V4.1 engine をビルドし、その engine のモデル初期化が要求リングを確保して CPU lane service thread を開始する必要があります。CMake では STRATA_BUILD_DSV41 の既定値は OFF で、HIP gfx906 では engine target を作りません。GPU backend なしの分岐が作るのは host-side benchmark だけです。
- 値の分岐は _WIN32 のコンパイル条件内にあります。したがって Windows の strata-dsv41 だけが DS4_LANE_NAP を読みます。Windows 10 version 1803 以降の高解像度 timer を意図したコードですが、作成できない場合は通常の sleep_for(20 us) に fallback します。
- service thread が要求を待ち始めてから、最後の応答後の spin 時間を超えた場合に休止処理へ入ります。その時間は別変数 DS4_LANE_SPIN_MS で決まり、既定値は 250 ms です。したがって DS4_LANE_NAP は応答直後の待機には作用しません。
- CLI 引数による上書きはこの engine の読み取り箇所にはありません。Strata server 経由では子 engine の環境を親の os.environ から複製し、設定の env 項目で同名値を上書きして渡す経路があります。

## 実行時の詳細

engine はモデル初期化時に service thread を作成し、その thread が serve_lane() を実行します。要求リングに次の要求がない間、thread は spin し、最後の応答から DS4_LANE_SPIN_MS を超えると休止します。Windows ではその箇所で static const bool hires を初めて評価し、DS4_LANE_NAP が未設定でなく、かつ値が厳密に sleep である場合に限り false になります。これは関数内 static に保存されるため、最初の評価後にプロセス環境を変更しても再評価されません。

hires が true の場合、コードは CreateWaitableTimerExW に CREATE_WAITABLE_TIMER_HIGH_RESOLUTION を渡して timer を作成します。作成に成功すれば相対 20 us で timer を設定し、最大 5 ms 待ちます。timer 作成が失敗した場合、または hires が false の場合は sleep_for(20 us) を呼びます。SetWaitableTimer / WaitForSingleObject の戻り値は検査せず、この箇所に成功・失敗ログもありません。

server から起動する場合、serve/server.py の child_env() は親環境の複製に config の env 項目を反映します。そのため親プロセスの値は通常継承され、config に DS4_LANE_NAP があれば config 値が優先します。engine 内での初回評価後に値を変えても、static cache のため反映されません。

## 根拠

- src/dsv41/ds4_model.cu:3131-3156 — decode request / response ring を確保し、CPU lane service thread を開始。
- src/dsv41/ds4_model.cu:7454-7481 — 要求待ち、spin 閾値、Windows 限定の値判定、timer 作成・待機と fallback。コメントでは Windows 10 1803 以降の高解像度 timer と説明。
- src/dsv41/ds4_model.cu:7632-7636 — 応答後に last を更新し、次のアイドル待ち時間を測る。
- CMakeLists.txt:906-920,2780-2786 — DeepSeek-V4.1 engine target は CUDA/HIP backend 側にあり、GPU backend なしでは host-side benchmark のみを作る。
- serve/server.py:3747-3763 — server の子 engine 環境を親から複製し、config env の値を反映。
- docs/DETAILS.md などの設計資料には、この変数についての個別説明・測定値を確認できませんでした。
