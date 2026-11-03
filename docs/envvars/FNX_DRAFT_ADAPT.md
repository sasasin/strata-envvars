# `FNX_DRAFT_ADAPT`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。調査対象 checkout は `## main...origin/main` で、開始時に未コミット変更はなかった。

## 役割

`strata-split` の単独セッション生成経路で、MTP draft chain の長さを受理率に合わせて選ぶか、`--spec` で指定した最大長 `K_` まで毎回作るかを切り替えます。適応を有効にしても、ngram lookup draft が見つかったラウンドは lookup の長さが使われ、この変数による MTP chain 長の選択には入りません（`src/split/src/session.cpp:566-579`）。

これは通常の `strata` エンジン全体の設定ではありません。split engine は `STRATA_BUILD_SPLIT=ON` の任意ビルドで作られる別実行ファイルであり、Linux CUDA/HIP の条件を満たさない場合や必要な GGML checkout がない場合は CMake が構築をスキップします（`src/split/CMakeLists.txt:1-5,20-30,64-77,92-103`）。

## 値と判定

`env_int("FNX_DRAFT_ADAPT", 1)` が `env_int` 共通 helper を通じて値全体を 10 進整数として読み、結果が 0 かどうかで判定します（`src/split/src/session.cpp:415`; `src/split/src/env.hpp:15-21,33-40`）。

| 環境変数 | 判定・動作 |
| --- | --- |
| 未設定 | 既定値 `1`。適応を有効にする |
| `0`（符号付き表記 `+0`、`-0` を含む） | 適応を無効にし、MTP chain 長を常に `K_` にする |
| 0 以外の有効な整数 | 適応を有効にする。正負を問わず、数値が 0 以外なら同じ扱い |
| 空文字、整数でない文字列、整数の後ろに余分な文字がある値、`long long` の範囲外 | `std::runtime_error`。値全体を parse するため、例 `1x` や空白は受理しない |

数値の上限・下限をこの変数用に追加制限する処理はありません。整数としての境界は `strtoll` の `long long` 範囲です。無効値を既定値へ置き換える処理もありません（`src/split/src/env.hpp:15-21,33-40`）。

## 有効になる条件

- `strata-split` または同じセッション実装を含む `split_fnx_run` がビルドされ、その生成処理で `Session::generate()` が呼ばれること。CMake は `session.cpp` をこの2系統のターゲットに含めます（`src/split/CMakeLists.txt:64-77,152-160`）。
- `Session::generate()` 内で MTP draft chain の経路に達すること。`speculate` が false なら draft を消去して次の round へ進むため chain は作られません。通常の `Session` の既定値は true です（`src/split/src/session.hpp:117-120`; `src/split/src/session.cpp:562-585`）。
- lookup draft が空であること。lookup が空でなければ、その drafts を次の round に使い、MTP chain 長の選択を行いません（`src/split/src/session.cpp:566-579`）。
- `--spec` が指定する `K_` が上限になります。適応時の長さは `K_` を超えず、適応無効時は `K_` 固定です。CLI にはこの環境変数を上書きする専用引数はありません（`src/split/tools/sfnx.cpp:67,86,440,454`; `src/split/src/session.cpp:419-426,576-579`）。

`sfnx` の複数スロット経路で `BatchDecoder` が使われる場合、この変数は同 decoder に渡されず、`BatchDecoder` 側の計画ロジックが動きます。`FNX_DRAFT_ADAPT` の直接参照は `Session::generate()` のみです（`src/split/tools/sfnx.cpp:438-445,646-666`; `src/split/src/batch.cpp:261-310`; `src/split/src/session.cpp:415`）。

## 実行時の詳細

`sfnx` サーバーの通常の `GEN` は `Session::generate()` を呼び、そこでは各生成要求の開始時に `env_int` を実行します。値は `static` に保存されないため、同一プロセスで後続の要求を始める前に環境が変更されれば次の要求では再読込されます。実行中の要求では、ローカル定数 `adapt` がその要求の間使われます（`src/split/tools/sfnx.cpp:793-816,839-847`; `src/split/src/session.cpp:397-416`）。

適応有効時は、各チェーン位置について `stood / tried`（初期値はそれぞれ `0.7 / 1.0`）を指数係数 `0.97` で更新し、各候補長の期待 token 数を定数で見積もった round/verify/draft 時間で割ります。最も高い率となる長さを選びます。初期推定では長さ `1..K_` を比較し、チェーンの4回ごとに一つ長い長さも試します。適応無効時は `K_` をそのまま選びます（`src/split/src/session.cpp:411-426,524-530,573-584`）。

環境値に不正な整数があると `env_int` は変数名と値を含む例外を投げます（例: `FNX_DRAFT_ADAPT: '1x' is not a whole number`）。単独 `GEN` の `generate()` 呼び出しは要求単位の例外捕捉の外にあり、サーバーループの捕捉から `fail()` に進みます。プロトコル出力に `ERR <例外文>`、stderr に `sfnx: failed: <例外文>` を出してプロセスを終了コード 1 で終了します（`src/split/src/env.hpp:33-40`; `src/split/tools/sfnx.cpp:839-847,1086-1095,1030-1035`）。

## 根拠

- 全直接参照は `src/split/src/session.cpp:414-415` の1箇所。索引の候補名が実際に読み取られていることを確認した。
- 数値全体の parse、unset 時の fallback、不正値例外: `src/split/src/env.hpp:15-21,33-40`。
- 適応長のスコア計算、固定長との分岐、chain 更新: `src/split/src/session.cpp:411-426,524-530,573-584`。
- split engine の別実行ファイルとビルド条件: `src/split/CMakeLists.txt:1-5,20-30,64-77,92-103`。設計資料も split engine を通常 engine とは別の opt-in engine と説明しています（`docs/SPLIT_ENGINE.md:1-5,79-82`）。
