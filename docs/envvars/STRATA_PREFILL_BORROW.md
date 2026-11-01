# `STRATA_PREFILL_BORROW`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

Windows の HIP 版を Strix Halo（GPU arch `gfx1151`）で使う場合に、prompt path が expert cache の末尾の slot を一時的に借りて buffer を置く既定動作へ戻します。この環境変数は、同条件で通常有効になる「buffer を別に確保して cache slot を借りない」既定変更を抑えます。prompt path が実際に借りるには、後述のとおり cache と expert profile などの条件も必要です。

全リポジトリの同名参照を確認したところ、値を読む Strata コードは `src/program/generate.cpp` の一箇所です。helper 経由や動的な名前での読み取りは見つかりませんでした。候補一覧には名前がありますが、単なる候補ではなく、Strata が起動時に値を読み分岐に使っています。

## 値と判定

文字列全体や数値としては parse せず、`getenv()` の結果の先頭文字だけを比較します。判定は `generate` の起動時に一度行われ、static cache はありません。

| `STRATA_PREFILL_BORROW` | gfx1151 Windows HIP でのこの分岐 |
|---|---|
| 未設定 | 自動的に借用を止め、prompt buffer を別確保する |
| 空文字 | 未設定と同じ。先頭文字が `'1'` ではないため自動的に借用を止める |
| 先頭文字が `'1'`（例: `1`, `10`, `1anything`） | 自動的な借用停止を抑える。通常の cache 借用条件が満たされれば借用する |
| その他（例: `0`, `true`, `false`, 空白で始まる値） | 自動的に借用を止める |

ただし、`STRATA_GFX1151_DEFAULTS` の先頭文字が `'0'` の場合は、この自動設定分岐自体が借用停止を設定しません。その場合、`STRATA_PREFILL_BORROW` の値によらず、この分岐から `no_prefill_borrow` は変更されません。`STRATA_GFX1151_DEFAULTS` の空文字や `'0'` 以外の値は、この抑止条件には該当しません。

## 有効になる条件

- `STRATA_USE_HIP` を定義したビルドであること。対象の判定は HIP 専用のコンパイル分岐内にあります。
- Windows ホストであること。
- 可視 GPU がすべて integrated と報告され、全 GPU の arch 名先頭 7 文字が同じで、その arch が `gfx1151` であること。GPU が複数ある場合も全台がこの条件を満たす必要があります。GPU 情報を取得できなければ、この判定ブロックは実行されません。
- 既定の借用停止を環境変数で抑えた後も、`--no-prefill-borrow` が指定されていれば借用しません。この CLI 引数は `no_prefill_borrow` を true にし、この環境変数は false に戻しません。
- `STRATA_GFX1151_DEFAULTS=0` は gfx1151 向けの自動調整を抑えます。ここでの判定も先頭文字のみです。
- 複数 GPU の layer split では `STRATA_SPLIT_OWN` によって prompt buffer を自前にする経路があります。cache 借用には expert profile と、prompt buffer を配置できる cache slot も必要です。

`STRATA_PREFILL_BORROW=1` は他の OS、CUDA / Metal ビルド、gfx1151 以外ではこの分岐に作用しません。また、値を `1` にしても既定の `--prefill auto` chunk や cache の空き状況、別の借用停止条件を上書きする指定にはなりません。

## 実行時の詳細

CLI 引数の読み取り後、engine の後続初期化に先立って HIP ビルドが GPU 情報を調べます（`src/program/generate.cpp:3383-3444`）。gfx1151 Windows の自動 chunk 調整では、借用停止が有効になると `prefill_own_keep_chunk` も true にします。このとき後段の `--prefill auto` fallback は chunk を 2048 に縮めず、既に選ばれた chunk を保ちます。借用停止を `STRATA_PREFILL_BORROW=1` で抑えた場合、この保持フラグも立たず、他の条件で auto が借用不能となれば通常の 2048 fallback が適用されます（`src/program/generate.cpp:3411-3425,3427-3441,3771-3776`）。

借用なしでは prompt buffer 用の VRAM を別に確保し、その分を cache から使えません。借用ありでは buffer を cache の末尾に配置し、prompt 後に借りた slot を expert cache 用に戻します。layer split の cache sizing でも、借用時は buffer 用の別枠を見積もらず、借用しない場合は reserve を計上します（`src/program/generate.cpp:5222-5239,9411-9420`）。

単一 GPU の通常 generate 経路では、`no_prefill_borrow` が false で、resident expert table と device cache があり、`--prefill` が chunk 処理を使う場合に借用計画を行います。借りる slot が決まると `strata generate: prompt path borrows ...`、借りなければ `strata generate: prompt path allocates its own buffers (no cache slots to borrow)` を stderr に出します。serve 経路でも cache 借用の成立時に借用 slot 数を、借用できない場合に自前 buffer のログを出します。したがって、環境変数の値だけで実際の借用や専用ログが保証されるわけではありません（`src/program/generate.cpp:17685-17767,9456-9462,9753-9783`）。

借用経路で prompt 初期化が失敗すると `strata generate: <理由>` を stderr に出して終了コード 1 になります。serve の stage / prompt 初期化失敗は経路により 1 または「do not fit」の場合 2 を返します。環境変数専用の警告、エラー、終了経路はありません（`src/program/generate.cpp:9800-9813,17761-17766`）。

## 根拠

- 同名環境変数の読み取りと gfx1151 条件: `src/program/generate.cpp:3383-3400,3432-3442`。
- CLI による借用停止、gfx1151 の自動 chunk 調整、auto fallback: `src/program/generate.cpp:3161-3190,3411-3441,3771-3776`。
- 借用時と非借用時の VRAM / cache sizing: `src/program/generate.cpp:5222-5239`。
- serve の借用条件と観測ログ: `src/program/generate.cpp:9456-9462,9753-9783`。
- 通常 generate の借用計画、ログ、初期化失敗: `src/program/generate.cpp:17685-17767`。
- gfx1151 defaults の `'0'` 判定: `src/core/arch_defaults.cpp:55-57`。
