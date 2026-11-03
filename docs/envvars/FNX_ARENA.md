# `FNX_ARENA`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。調査開始時の作業ツリーは `main...origin/main` で、未コミット変更はありません。

## 役割

`strata-split` の sFNX エンジンで、最大の expert pool の VRAM slot を K/V pool が借りて拡張する arena 機能を選びます。未設定時は有効です。無効にすると expert slot を K/V pool に貸さず、K/V pool は独立した VRAM allocation になります。これはレイヤー分割等の全 Strata エンジン共通設定ではなく、`src/split` のモデル・エンジン経路で使われます。

`FNX_ARENA=1` でも expert RAM cache が無効なら起動できません。arena は cache の expert slot を借りる機能であり、`FNX_EXPERT_RAM_GIB=off` と併用する場合は `FNX_ARENA=0` が必要です（`src/split/src/model.cpp:1474-1488`）。

## 値と判定

| 値 | 判定 |
|---|---|
| 未設定 | 有効。`arena = !arena_s || ...` により既定で ON。 |
| `1` | 有効。 |
| `0` | 無効。 |
| 空文字、`true`、`false`、空白付き、その他の文字列 | 無効値として例外。文字列全体を `strcmp` で比較し、数値変換や前後空白の除去はしない。 |

大文字小文字を変えた `TRUE` 等も受理されません。設定時に許される文字列は厳密に `0` と `1` の二つです。判定は `src/split/src/model.cpp:1476-1479` にあります。

## 有効になる条件

- **実行経路:** `Model::choose_residency()` が呼ばれる sFNX モデル経路で有効です。通常の plain load は `FNX_27B` が偽のビルドでこの関数をモデル読み込み中に呼びます（`src/split/src/model.cpp:1441-1443`）。sFNX の CMake ターゲットは `FNX_27B=0` を定義しています（`src/split/CMakeLists.txt:102-113`）。`FNX_27B` が真の plain-load 経路ではこの箇所から `choose_residency()` を呼ばないため、`FNX_ARENA` は読み取られません。
- **他の環境変数:** `FNX_EXPERT_RAM_GIB` の既定は 3 GiB cache ありです。値が厳密に `off` なら cache 無しとなり、arena が有効の場合は `fnx: FNX_EXPERT_RAM_GIB=off needs FNX_ARENA=0 ...` で拒否します（`src/split/src/model.cpp:1475-1488`）。cache があると expert profile を読み、既定の `data/expert-routes.bin` または `FNX_EXPERT_PROFILE` の順位で expert residency を決めます（同 `:1489-1518`）。
- **arena の容量:** arena 有効時に限り `FNX_ARENA_RESERVE_MIB`（既定 512 MiB）と、設定されていれば `FNX_ARENA_BASE_PAGES` が容量計算に使われます。これらは arena 自体の ON/OFF を変えません（`src/split/src/engine.cu:276-286,329-345`）。
- **CLI:** `FNX_ARENA` を読む CLI 引数は見つかりませんでした。通常の run-config から自動選択される all-cards split engine では、ラッパーが既存の `env` をマージした後に `FNX_ARENA=0` と `FNX_EXPERT_RAM_GIB=off` を設定するため、親環境やプロフィールの `FNX_ARENA` 値はその子プロセスでは上書きされます（`strata_control/split_engine.py:250-264`）。`child_env()` は config の env を子環境に適用します（`serve/server.py:4054-4068`）。このラッパー経路では arena は意図的に使われません。
- **モデル・要求状態:** 値はモデルの residency / expert placement と Engine 初期化に反映されます。個々の request で有効・無効を切り替える処理はありません。

## 実行時の詳細

### 値の読み取りと反映

`choose_residency()` は `std::getenv("FNX_ARENA")` で直接読み、関数内の `static` には保存しません（`src/split/src/model.cpp:1469-1479`）。通常の sFNX plain load ではモデルの初期化中に一度呼ばれます。`place_experts()` も同じ関数を呼ぶため、VRAM 不足時に expert allocation を解放して再配置する経路では再読込されます（同 `:1441-1443,1550-1565`; `src/split/src/engine.cu:290-315`）。通常は Engine 作成後の request ごとには読み直しません。

### arena 有効時

resident expert のうち最大サイズの pool では、profile 順で冷たい slot を arena 用に取り置き、初期配置時に割当・充填しません（`src/split/src/model.cpp:319-323,339-357`; `src/split/src/model.cpp:1562-1565`）。Engine は既存の prompt / draft 用 buffer 確保後にカードごとの空き VRAM、expert slot、reserve、lane の block を使って初期 K/V page 数を見積もります（`src/split/src/engine.cu:274-328`）。`FNX_ARENA_BASE_PAGES` が設定されていれば、計算された範囲内で初期 page 数を指定できます。初期 K/V pool と expert slot は同じ allocation の領域になり、K/V pool の拡張時に expert slot を貸し、縮小時に返します。貸せる範囲は、各カードで少なくとも `2 * MAXT * TOPK` slot を残す制限を受けます（同 `:329-345`; `src/split/src/engine.hpp:252-254`; `src/split/src/engine.cu:551-592,618-625`）。

開始時の stderr には各カードの arena 後の空き VRAM と、K/V pool の own pages・最大 pages・貸し元 pool の slot 数が出ます（`src/split/src/engine.cu:355-366,397-409`）。拡張・返却時には `fnx: arena: K/V pool ...; slots lent ...` が出ます（同 `:590-592`）。

### arena 無効時と失敗

`FNX_ARENA=0` では arena の共有 allocation と expert slot の貸し借りを行わず、Engine は通常の K/V pool allocation と prefill stages の経路に進みます（`src/split/src/engine.cu:283,347-370`）。

設定値が `0` / `1` 以外なら `choose_residency()` が例外を投げます。sFNX の起動処理は `ERR <理由>` を stdout に出し、stderr に `sfnx: failed: <理由>` を出して終了コード 1 で終了します（`src/split/tools/sfnx.cpp:1050-1062,1027-1035`）。server が all-cards split engine の起動に失敗した場合は、その理由を含む一行を出し、保持していた通常の layer-split 設定で起動を試みます（`serve/server.py:9107-9144`）。また、arena 初期化時に pool がない、VRAM 不足が 8 回の再配置後も解消しない、または slot・reserve・lane block が収まらない場合も例外になります（`src/split/src/engine.cu:290-328`）。

## 根拠

- 全参照を `rg -n --hidden --glob '!.git/**' 'FNX_ARENA'` で確認しました。実環境から対象値を読む実装は `src/split/src/model.cpp:1476` のみです。残りのコード参照は arena の説明コメント、別変数 `FNX_ARENA_*`、自動起動ラッパーによる env の設定、またはテストです。
- 直接読み取り・値判定・`FNX_EXPERT_RAM_GIB` との条件: `src/split/src/model.cpp:1469-1489`。
- ExpertCache の pool 選択と slot の配置: `src/split/src/model.cpp:319-365,1550-1565`。
- arena の容量計算、初期 allocation、貸し借り、ログ: `src/split/src/engine.cu:276-409,448-592,618-625`。
- 通常の all-cards split wrapper による値の固定と子環境への反映: `strata_control/split_engine.py:250-264`; `serve/server.py:4054-4068`。
- 起動失敗の通知と通常 engine への fallback: `src/split/tools/sfnx.cpp:1027-1035,1050-1062`; `serve/server.py:9107-9144`。
