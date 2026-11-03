# `FNX_BATCH_DRAFTS`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。調査開始時の作業ツリーは `main...origin/main` で、未コミット変更はありませんでした。

## 役割

Strata の opt-in 分割エンジン sFNX において、複数 lane の batched decoding window に何をドラフト行として載せるかを選びます。`0` はドラフトなし、`lookup` は各 lane の n-gram lookup draft のみ、`1` または未設定は lookup に加えて必要に応じ draft layer（MTP）の連鎖も使います。これは通常の Strata エンジン全体の設定ではなく、`src/split` の sFNX とその `split_fnx_run` ドライバーにある設定です。sFNX は Linux CUDA/HIP 向けのビルドオプション `STRATA_BUILD_SPLIT` で追加され、既定ではビルドされません（`src/split/CMakeLists.txt:1-7,20-30,64-80,153-165`）。

## 値と判定

値は `std::getenv` の文字列全体を `strcmp` で大文字小文字を区別して比較します。数値変換、空白除去、部分一致はありません。未設定だけが既定値となり、空文字は無効値です。

| 環境値 | 判定 | batched window のドラフト |
|---|---|---|
| 未設定 | 既定で `mtp` | lookup に加え、lookup が使えない lane では MTP draft layer の chain を使う |
| `1` | `mtp` | 未設定と同じ |
| `lookup` | `lookup` | n-gram lookup draft のみ。MTP chain は作らない |
| `0` | `off` | draft 行を使わない |
| 空文字、`true`、`01`、`Lookup`、前後に空白がある値など | 無効 | `FNX_BATCH_DRAFTS: 0, lookup or 1, not '<値>'` の例外 |

根拠: `src/split/src/engine_common.cu:1020-1028`。値は関数内の `static const` に保存され、最初の呼び出しで評価されます。同じプロセス内で環境を変更しても、その後は再読込されません。初期化時に不正値で例外が出た場合は設定値のキャッシュが成立せず、例外は呼出元へ伝わります。

## 有効になる条件

- sFNX 自体がビルドされていることが前提です。CMake は Linux CUDA または HIP のみを対象とし、`STRATA_BUILD_SPLIT` が有効でなければ split engine を追加しません。CUDA/HIP のどちらでもこの変数の文字列判定は同じです（`src/split/CMakeLists.txt:1-7,20-30,64-80`）。
- sFNX サーバーで draft 付きバッチ生成を使うには `--serve` と `--batch` が必要で、`--batch` は 1 以上に制限されています。`--batch` が 1 の場合は `BatchDecoder` を作らず、2 以上かつ本変数が `0` 以外の場合にだけ作ります（`src/split/tools/sfnx.cpp:72-104,435-446`）。`--batch` は lane/slot 数を決める CLI 引数で、本変数を上書きしません。
- `--batch >= 2` でも本変数が `0` なら、sFNX は `BatchDecoder` を使わず `Engine::step` で各 lane を一行ずつ進めます。BGEN/BGENI の入力自体は `--batch` が 2 以上なら受け付けられます（`src/split/tools/sfnx.cpp:646-720,975-997`）。
- `split_fnx_run` の `bdecode` は `0` を許さず、stderr に `bdecode: set FNX_BATCH_DRAFTS (lookup or 1)` を出して status 2 で戻ります（`src/split/tools/fnx_run.cpp:646-655`）。
- MTP chain を使うには実行経路で draft layer が Engine に attach されている必要があります。sFNX サーバーは `--mtp` を必須として読み込み、Engine に attach します（`src/split/tools/sfnx.cpp:81-104,1050-1060`）。`split_fnx_run` の `bdecode` も MTP データを作って attach します（`src/split/tools/fnx_run.cpp:655-658`）。一方、`lookup` モードでは BatchDecoder は MTP chain を使わず lookup draft のみを割り当てます（`src/split/src/batch.cpp:261-285,325-355`）。

## 実行時の詳細

`BatchDrafts` の値は `src/split/src/engine.hpp:29-36` で `off`、`lookup`、`mtp` として宣言されています。バッチデコーダーは各 lane の lookup draft を算出し、`lookup` モードではそれを割り当てて終了します。`mtp` モードでは MTP layer の draft を得て、lookup の先頭がその draft と一致すれば lookup 列を採用し、一致しなければ MTP chain を作ります。lookup がない場合も MTP chain を使います（`src/split/src/batch.cpp:261-285,325-369`）。window の行は `Engine::verify_rows` で検証され、各 lane で受理された draft の後続 token が出力されます（`src/split/src/batch.cpp:120-162,218-256`）。

設定の初回評価は特定の呼び出し順に依存します。sFNX サーバーでは `Server` 構築中に、複数 slot なら `BatchDecoder` 選択時に参照され、`Engine::warm_graphs()` も batched graph の準備可否を判定する際に参照します（`src/split/tools/sfnx.cpp:435-446`; `src/split/src/engine_common.cu:328-385`）。したがって不正値は、モデル読み込み後の warm-up/Server 初期化時に例外になります。sFNX の初期化失敗は `ERR <理由>` を標準出力、`sfnx: failed: <理由>` を標準エラーに出し、status 1 で終了します（`src/split/tools/sfnx.cpp:1027-1035,1050-1065,1087-1092`）。

## 根拠

- 変数の唯一の実読取箇所と値判定: `src/split/src/engine_common.cu:1020-1028`。他の一致箇所は enum/挙動の説明コメント、BatchDecoder のエラー、または呼び出し側です。
- モード定義: `src/split/src/engine.hpp:29-36`。
- モード別ドラフト生成: `src/split/src/batch.cpp:64-86,261-355`。
- sFNX サーバーでの初期化、バッチ有無の分岐、BGEN 入力: `src/split/tools/sfnx.cpp:435-446,646-720,975-997`。
- `bdecode` の off 時の終了: `src/split/tools/fnx_run.cpp:646-655`。
- `docs/DETAILS.md` にはこの環境変数の記載はありません（調査対象 commit で `FNX_BATCH_DRAFTS`、sFNX の batched draft 動作に関する記述を検索）。性能値や通常の Strata 実行経路への適用は、この変数の説明として確認できませんでした。
