# `STRATA_INK_TAP_VISITS`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

## 役割

HIP 版 `strata-inkling` が trunk の中間状態を tap として取得する訪問番号を、既定の4点から指定の4点へ差し替える診断用変数です。HIP バックエンドの `HipBackend::init()` が `dspark_cfg_.target_visits` の先頭4要素を書き換え、その設定を trunk の tap コピー処理が参照します。値の読み取りには `--spec-check` の条件分岐がありません。通常のサーバー推論では DSpark 用 tap を取得するときに効き、`TapCapture` を要求する診断経路でも取得点が変わります（`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:555-578,3639-3645`）。

この変数自体は tap のコピー先を選ぶもので、trunk の計算や CLI のドラフト有効化を直接切り替えません。選んだ tap は DSpark の context 計算にも入力されるため、DSpark が有効な実行ではドラフト用状態に影響します（`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:3565-3577,4971-5020`）。

## 値と判定

HIP `init()` は変数が設定されていて先頭文字が NUL でなく、モデル設定の `target_visits` が4個以上ある場合に解析します。したがって未設定・空文字・モデル側の点が4個未満なら既存設定を維持します。モデル設定に `target_layer_ids` がなければ既定は `[5, 23, 41, 48]` ですが、manifest の指定があればその値が元になります（`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:568-578`; `engine/src/inkling2/ink_manifest.h:182-183,291-294`）。

解析は `strtol(q, &ee, 10)` を繰り返し、変換できなかった位置で停止します。値の後ろがカンマなら次へ進み、それ以外は同じ位置を次の反復で調べて停止します。最終的に整数をちょうど4個集めた場合に限り、先頭4要素を置き換えます。先頭空白・符号は `strtol` の規則で受け付け、基数10で整数の先頭部分を変換します。大文字小文字の概念はありません。各値の範囲や訪問番号としての妥当性、変換時の `errno` は検査されません。変換後は `long` から `int` へキャストされます。4個目の後ろに残る文字は解析停止後に検査されず、4個目が変換できた時点で4要素を適用します（同: `568-578`）。

| 条件 | 未設定・空文字 | 有効になる値の例 | 無効・適用されない例 |
|---|---|---|---|
| HIP `HipBackend::init()`、モデルの `target_visits` が4個以上 | 現在のモデル設定を維持 | `5,23,41,48`、`0,1,2,3`、`1, 2, 3, 4`（各整数前の空白は許容）、`1,2,3,4,`、`1,2,3,4junk` | `1,2,3`（4個未満）、`1,2,x,4`（4個未満しか変換できない）、`1,2,3,4,5`（5個となる） |
| HIP `HipBackend::init()`、モデルの `target_visits` が4個未満 | モデル設定を維持 | なし（解析分岐に入らない） | 設定値の内容にかかわらず適用されない |

無効・不完全な文字列もエラーにはせず、解析結果がちょうど4個でなければ元の `target_visits` をそのまま使います。番号の正負やモデルの訪問範囲外かどうかを検証する処理はありません（`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:568-578`）。

## 有効になる条件

- この読み取りは `engine/src/inkling2/hip/ink_hip_backend.hip.cpp` にある HIP 実装です。HIP がビルドに含まれない構成では、この読み取りコードは実行対象になりません（HIP サブディレクトリの追加条件: `engine/src/inkling2/CMakeLists.txt:240-242`）。
- `HipBackend::init()` が呼ばれれば、変数の解析はモデル設定のコピー直後に行われます。`--spec-check` 専用の判定ではなく、通常起動でも読みます（`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:555-578`）。
- tap のコピーが実行されるには、forward 処理で `need_taps` が真である必要があります。これは `taps_out != nullptr`、または `has_dspark_ && batch.capture_taps` の場合です（同: `3571-3577,3639-3645`）。`has_dspark_` は `opts.enable_dspark && dspark_cfg_.present` で決まり、DSpark モデル情報と有効化設定の両方が必要です（同: `893-895`）。
- `--spec-check` は `enable_dspark` を true にし、比較中に `capture_taps` を設定します。実際の tap 取得比較では `TapCapture` も渡されます（`engine/src/inkling2/ink_main.cpp:599-623,784-806`）。
- 通常の `strata-inkling` では `--draft off` が `enable_dspark` を false にします。サーバーでの `use_dspark` も draft mode・モデル内 DSpark・バックエンドの準備完了を条件にします。この場合、通常のサーバー経路は DSpark 用 tap を要求しません。ただし `TapCapture` を明示的に渡す診断呼び出しでは別です（`engine/src/inkling2/ink_main.cpp:895-898`; `engine/src/inkling2/ink_serve.h:507,1003-1007`）。
- 訪問番号が trunk の実際の `visit_id` に一致しなければ、その tap のコピー条件は成立しません。コピー側は番号の範囲補正や不一致時の代替訪問を行いません（`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:3639-3645`）。

## 実行時の詳細

環境は各 `HipBackend::init()` の都度 `std::getenv` で読み取られ、関数 static などへの cache はありません。したがってバックエンドを初期化し直すときはその時点の値を読みますが、同じ初期化済みバックエンドで環境を後から変更しても、すでに `dspark_cfg_.target_visits` に反映された値は再読込されません（`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:555-578`）。

モデルの DSpark 設定を `dspark_cfg_` に複製した後、条件を満たせば最初の4訪問番号を上書きします。forward 中の `maybe_tap` は `need_taps` が真のとき、各 `visit_id` をその4要素と照合し、一致した tap のベクトルを GPU バッファへコピーします。通常の DSpark context 更新は4つのバッファを融合計算へ渡し、各層の K/V と recurrent state を更新します（同: `568-578,3639-3645,3565-3568,4971-5020`）。診断の `TapCapture` 要求時は同じ4バッファが host へコピーされます（同: `4895-4900`）。

この値を CLI 引数や他の環境変数で再上書きするコードは確認できません。`--draft` は DSpark の有効化状態を変えますが、tap 訪問番号そのものは変更しません（`engine/src/inkling2/ink_main.cpp:895-898`）。

## ログと測定値

この変数の解析成功・失敗・不完全値について専用ログや警告はありません。解析値が4個でなければ既存設定のまま続行し、値の不一致自体で初期化エラーにはしません（`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:568-578`）。tap バッファ取得時の HIP コピー失敗はこの箇所で戻り値を破棄しており、この変数専用の失敗表示はありません（同: `3639-3645`）。この変数の効果を定量化する測定値は調査対象ソースに記載されていません。

## 根拠

- 読み取り・値の解析・適用条件: `engine/src/inkling2/hip/ink_hip_backend.hip.cpp:555-578`
- モデル側 tap 訪問番号と manifest の上書き: `engine/src/inkling2/ink_manifest.h:182-183,291-294`
- tap の有効条件・訪問番号一致時のコピー: `engine/src/inkling2/hip/ink_hip_backend.hip.cpp:3565-3577,3639-3645`
- DSpark context での tap 使用: `engine/src/inkling2/hip/ink_hip_backend.hip.cpp:4971-5020`
- HIP ビルド条件: `engine/src/inkling2/CMakeLists.txt:240-242`
- `--spec-check` と `--draft off` の設定: `engine/src/inkling2/ink_main.cpp:599-623,895-898`
