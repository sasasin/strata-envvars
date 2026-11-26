# `STRATA_PF_PEER_COMPACT`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`--peer-device` を使う prompt 処理で、peer GPU に割り当てた expert rows の作業バッファを、layer 全体分確保する従来経路か、expert group ごとの compact 経路にするかを選ぶ。既定は compact。compact では group（最大 `MMQ_GROUP` experts、合計最大 chunk token 数 `G` rows）ごとに計算し、出力 rows は double buffer を使う。CUDA/HIP と SYCL の両方に実装がある（`engine/src/prefill/prefill.cpp:1338-1343,3412-3465`; `engine/sycl/src/prefill/prefill.cpp:672-677,2307-2354,4331-4343`）。

この設定は peer prompt 経路の有効化そのものや生成設定を選ぶものではない。`--peer-device` の peer が有効で、`--peer-prefill-rows` が 0 以外のときに `Prefill::set_peer` が呼ばれて初めて読み取られる。生成側がこれらの条件を満たさない場合は読み取られない（CUDA/HIP: `engine/src/program/generate.cpp:13143-13153`; SYCL: `engine/sycl/src/program/generate.cpp:7608-7613`）。

## 値と判定

両実装とも `std::getenv` の値を `std::atoi` に渡し、変換結果が 0 なら compact を無効、0 以外なら有効にする。文字列全体の妥当性検査はなく、`atoi` が先頭から変換できる整数部分だけを使う。したがって空文字、`0`、`0anything`、整数に変換できない文字列は 0 となり無効、`1`、`-1`、`2tail` はそれぞれ非 0 となり有効。前後空白は `atoi` の変換規則に従う。整数範囲外の入力に対する挙動はこのコードで定義・検査されない。

| backend / 条件 | unset | compact 有効 | compact 無効 |
|---|---|---|---|
| CUDA/HIP、P2P あり | 有効 | `atoi(value) != 0` | `atoi(value) == 0` |
| CUDA/HIP、P2P なし | 有効 | どの値でも有効（強制） | 無効にはできない |
| SYCL（P2P が必須） | 有効 | `atoi(value) != 0` | `atoi(value) == 0` |

CUDA/HIP は `|| !pp->p2p` によって P2P がない場合に compact を強制する。SYCL は `set_peer` の先行条件で P2P がないと拒否するため、P2P なしの compact 判定には到達しない（`engine/src/prefill/prefill.cpp:3333-3339,3412-3414`; `engine/sycl/src/prefill/prefill.cpp:2243-2249,2307-2309`）。

## 有効になる条件

- `--peer-device` で有効な peer があり、`--peer-prefill-rows` が 0 以外であること。CLI は peer 経路と初期 row 上限を決めるが、環境変数の値を上書きしない。compact が有効なら CUDA/HIP と SYCL の双方で `cap_rows` は `T_max * K` に置き換わり、指定された row 上限はこの上限としては使われない（`engine/src/program/generate.cpp:13143-13150`; `engine/sycl/src/program/generate.cpp:7608-7611`; CUDA/HIP: `engine/src/prefill/prefill.cpp:3373-3378,3415-3417`; SYCL: `engine/sycl/src/prefill/prefill.cpp:2249-2253,2310-2313`）。
- peer prompt の実装条件も満たすこと。CUDA/HIP では有効な peer、対象 layer に int8 または MMQ prompt kernel があることなどを検査し、条件を満たす layer がなければ `set_peer` は失敗する。P2P がない場合は `STRATA_PF_PEER_HOST` が `0` でないことも必要。SYCL は P2P と MMQ prompt path が必要（`engine/src/prefill/prefill.cpp:3333-3362`; `engine/sycl/src/prefill/prefill.cpp:2243-2249`）。
- prompt の処理時にも peer が当該 layer の計算対象となること。割り当てが設定されても、peer が担当する expert rows がない layer では compact group 処理は行われない（CUDA/HIP: `engine/src/prefill/prefill.cpp:6059-6065,6670`; SYCL: `engine/sycl/src/prefill/prefill.cpp:4330-4343`）。
- 環境値を読む箇所は CUDA/HIP `engine/src/prefill/prefill.cpp` と SYCL `engine/sycl/src/prefill/prefill.cpp` のみ。Metal、CPU、同梱ツール、stage helper の設定経路で本名を読む実装は見つからなかった。層分割の stage helper は `PeerPrefill` の既定値を使い、本変数の読み取りを通らない（helper の設定: `engine/src/prefill/prefill.cpp:3221-3240`; SYCL: `engine/sycl/src/prefill/prefill.cpp:2091-2130`）。

## 実行時の詳細

値は `Prefill::set_peer` が peer prompt 用 `PeerPrefill` を作るたびに読み、構造体の `compact` に保持する。static cache はなく、各要求でなく prompt path の設定時の評価である。serve の prompt path を再レイアウトすると `set_peer` を再実行して再評価する。実行中にプロセス環境を変更した場合の反映は、既に設定済みの `PeerPrefill` には起きない（`engine/src/prefill/prefill.cpp:3412-3414`; `engine/sycl/src/prefill/prefill.cpp:2307-2309`; 再設定箇所 `engine/src/program/generate.cpp:13143-13150`）。

compact 有効時は `cap_rows = T_max * K`、`G = T_max` とし、group 単位の `Xq_g` / `Hq_g` / `GU_g` / `H_g` / `Dm_b[2]` 等を確保する。実行時は peer の expert を group に分けて処理する。無効時は初期の `cap_rows` を保ち、`Xq` / `Hq` / `GU` / `H` / `Dm` の layer-sized buffer を確保する（CUDA/HIP: `engine/src/prefill/prefill.cpp:3415-3465,6670`; SYCL: `engine/sycl/src/prefill/prefill.cpp:2310-2354,4331-4343`）。この差分は peer 作業バッファと row 上限に関するもので、生成 token の同一性をこの調査で測定・検証したものではない。

CUDA/HIP は P2P なしの mapped-host route を許可する構成があり、その経路では `compact` が強制される。SYCL は P2P なしを `set_peer` で拒否する。CLI の `--peer-device` と `--peer-prefill-rows` は環境値に優先して compact を切り替える機能ではなく、前者は peer を選び、後者は compact 無効時に残る初期 row 上限にも関わる。

## ログと測定値

peer の設定に成功すると stderr に `strata prefill: peer GPU ...` の行が出る。compact 有効時は `, compact group buffers` が含まれ、peer streaming も設定される場合は追加で ring 情報が出る。compact 無効時はその語句が付かない（CUDA/HIP: `engine/src/prefill/prefill.cpp:3534-3545`; SYCL: `engine/sycl/src/prefill/prefill.cpp:2381-2386`）。設定失敗時、生成側は `strata serve: <理由> - the prompt path stays on the primary GPU` を stderr に出して peer prompt を使わず続行する（CUDA/HIP: `engine/src/program/generate.cpp:13147-13153`; SYCL: `engine/sycl/src/program/generate.cpp:7608-7613`）。SYCL で `sycl::exception` を catch した経路は例外内容と位置を stderr に出して `exit(1)` する（`engine/sycl/src/prefill/prefill.cpp:2389-2392`）。

コードコメントには 8192-token chunk の helper card 使用量について `~0.9 GB -> ~0.26 GB` という記述があるが、機種・backend・モデル・量子化・測定条件が示されていないため、一般的な測定値としては扱わない（CUDA/HIP: `engine/src/prefill/prefill.cpp:1338-1342`; SYCL: `engine/sycl/src/prefill/prefill.cpp:672-676`）。`docs/DETAILS.md` と `docs/SETTINGS.md` にこの変数の説明は見つからなかった。`terminal/data/settings-register.json` は両 backend の読み取り位置と parse を登録しているが、環境値を読む実装ではない（`terminal/data/settings-register.json:31973-32009`）。

## 根拠

- 全参照検索では、実際の環境読み取りは CUDA/HIP と SYCL の `std::getenv` 2 箇所。その他は `PeerPrefill` の説明コメント 2 箇所と設定レジストリで、helper 経由・動的な名前渡しの追加読み取りは確認されなかった: `engine/src/prefill/prefill.cpp:1341,3412`; `engine/sycl/src/prefill/prefill.cpp:675,2307`; `terminal/data/settings-register.json:31973-32009`。
- CUDA/HIP の値判定、compact buffer と layer-sized buffer: `engine/src/prefill/prefill.cpp:3412-3465`。
- SYCL の値判定、compact buffer と layer-sized buffer: `engine/sycl/src/prefill/prefill.cpp:2307-2354`。
- peer prompt を呼ぶ CLI 条件、失敗時の継続: `engine/src/program/generate.cpp:13143-13153`; `engine/sycl/src/program/generate.cpp:7608-7613`。
- `--peer-device`・`--peer-prefill-rows` と `set_peer` の成立条件: `engine/src/prefill/prefill.cpp:3333-3378`; `engine/sycl/src/prefill/prefill.cpp:2243-2253`。
