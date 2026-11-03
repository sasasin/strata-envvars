# `STRATA_DS4_DISK_SKIP_AUTO`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

DeepSeek-V4.1 用の `strata-dsv41` で、`STRATA_DS4_DISK_SKIP_W` による軽量 expert の読み飛ばしを、モデルが冷えている間だけ行う自動切替を有効にします。自動切替を使わない場合、`DISK_SKIP_W` の条件に合う読み飛ばしはリクエストをまたいで続きます。この変数を有効にすると、実行中に冷たい expert の割合が十分に下がった時点で読み飛ばしを止め、後続リクエストの開始時にページが RAM から失われていれば再開します。

## 値と判定

モデル実装内の `env_f(name, default)` は、変数が未設定なら default、設定されていれば `std::atof()` の結果を返します。対象変数の default は `0.0f` で、その値が `0.0f` と異なるかを判定します。文字列全体の検証やエラー報告はありません。

| 環境値 | `disk_skip_auto` |
|---|---|
| 未設定 | 無効（`0.0f`） |
| 空文字、数値に変換できない文字列、`0` / `0.0` | 無効（`atof` が 0） |
| `1`、`-1`、`0.5` など、`atof` の結果が 0 以外 | 有効 |
| 数値の後ろに文字が続く値（例: `1xyz`） | 数値の先頭部分が変換され、結果が 0 以外なら有効 |

`nan` のように `atof` が NaN を返す値も `!= 0.0f` を満たします。値の範囲制限はありません。ただし、実際の自動切替フラグは `STRATA_DS4_DISK_SKIP_W` の値が正の場合に限り有効です。`DISK_SKIP_W` が未設定・空文字・無効文字列・0・負値なら、対象変数を有効にしても自動切替は無効です。

## 有効になる条件

- `STRATA_BUILD_DSV41=ON` で `strata-dsv41` をビルドした場合にだけ、このモデル実装が実行ファイルに含まれます。CMake の既定値は OFF です。CUDA/HIP の GPU runtime にリンクする独立実行ファイルであり、通常の `strata` 実行ファイルにはこの経路は組み込まれていません（`CMakeLists.txt:931-945,958-972`）。
- `STRATA_DS4_DISK_SKIP_W` が正である必要があります。さらに、通常の decode の非 MTP layer で、layer index が `STRATA_DS4_DISK_SKIP_FROM` 以上かつ `g.nl` 未満であることが必要です。
- 実際に expert を飛ばすのは CPU lane に割り当てられ、かつその expert のページが RAM にない場合です。`DISK_SKIP_W` が各 routed expert の route weight 合計に対する閾値を決めます。自動切替フラグはこの既存の読み飛ばし条件を有効化するものではなく、読み飛ばす期間を制御します。
- prompt 経路の読み飛ばしではなく、decode 側で使われます。CLI とサーバーの双方で、リクエストを開始するタイミングに `begin_request()` が呼ばれます。

## 実行時の詳細

環境値はモデル実装の `disk_skip_auto` メンバー初期化時に読み取られ、そのモデルインスタンスの間は再評価されません。設定をモデル起動後に変更しても反映されません。自動状態 `sk_auto.on` は初期値 true で、最初のリクエストから条件付き読み飛ばしを行います。

各 decode layer について、route weight 合計に対して閾値以上の routed expert を「heavy」と数え、そのうち CPU lane にあり RAM にないものを冷たい expert と数えます。直近 `STRATA_DS4_DISK_SKIP_WINDOW` の token 分（既定 32。内部では対象 layer 数を掛けた token 数）の窓を集計し、`STRATA_DS4_DISK_SKIP_FROM` の layer で判定します。次のいずれかで、その回答の途中でも自動状態を OFF にします。

- 経過 token 数が `STRATA_DS4_DISK_SKIP_BUDGET` 以上（既定 512）
- 窓が満ち、冷たい expert の割合が 2% 以下
- 窓が満ち、冷たい割合の新しい最低値が 5% 以上改善しない状態が `STRATA_DS4_DISK_SKIP_SETTLE` token 続く（既定 64）

窓・settle・budget の値は `env_f()` で読み、コード上でそれぞれ最小 4・4・1 に clamp されます。整数化は `float` から `int` へのキャストです。

OFF 後は次のリクエスト開始時だけ再開を検討します。最後に記録された CPU lane expert が 64 件以上ある場合に、その expert 群のページが RAM に残っている割合を確認し、50% 未満なら自動状態を ON に戻します。リクエスト途中では再開しません。したがって RAM に残る割合が 50% 以上なら OFF が続きます。

この値の parse による警告・終了経路はありません。切替時は stderr に `ds4: DISK_SKIP auto: off after ...` または `ds4: DISK_SKIP auto: on again for request ...` が出ます。`strata-dsv41` の `STAT` 行には `skip_on=1/0` が付き、終了時には `DISK_SKIP auto: on/off at the end, ... switches` が出ます。実際に expert を飛ばした場合は `STAT` に `skipped=...`、decode 統計に `decode left out ... experts a token not in RAM ...` が出ます。

## 根拠

- 候補名の全参照と値判定: `src/dsv41/ds4_model.cu:1352,1427-1445`。`env_f()` の `getenv` / `atof` と default `0.0f` 比較、および関連する `DISK_SKIP_W` の初期化を確認。
- 適用対象と decode 条件: `src/dsv41/ds4_model.cu:9460-9465,9483-9511`。MTP 除外、layer 範囲、CPU lane / RAM 判定、route weight 条件と skip counter 更新。
- lookahead 済み expert の RAM 状態記録: `src/dsv41/ds4_model.cu:9366-9373`。
- 自動 OFF の窓計算・判定とログ: `src/dsv41/ds4_model.cu:1458-1489`。
- リクエスト間の再開判定: `src/dsv41/ds4_model.cu:1490-1520`; CLI 呼び出し `src/dsv41/ds4_main.cpp:1375-1377`、サーバー呼び出し `src/dsv41/ds4_main.cpp:1843-1847`。
- 観測可能な統計: `src/dsv41/ds4_main.cpp:993-999,2811-2814,2829-2831`。
- 独立 executable と既定 OFF の build 条件: `CMakeLists.txt:931-945,958-972`。
