# `STRATA_BATCH_MTP`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリの環境変数は対象外。

## 役割

バッチ推論の各 slot に MTP drafter を用意し、各検証 window で通常の次 token に加えて draft の提案を1個検証します。提案が採用された場合は、その window で2 token まで進めます。これは opt-in で、通常の batch 動作では slot の MTP draft を使いません。

環境変数は `strata generate` の起動時に一度読みます。CLI の `--batch-mtp` も同じ機能を有効にし、どちらか一方が有効なら要求状態になります。サーバーの `parallel_args()` も環境変数を参照しますが、そこでは `parallel` が8を超える場合の案内ログを出すかだけを判定します。実際に MTP batch を有効にする判定は engine 側です。

## 値と判定

engine は `getenv()` の値全体を parse せず、空でない値の先頭文字が `0` かを判定します。環境変数が未設定、空文字、または `0` で始まる文字列なら、この変数による opt-in は無効です。それ以外は有効です。大文字小文字、数値としての妥当性、後続文字は調べません。

| 値 | engine での判定 |
|---|---|
| unset、空文字 | 無効（既定） |
| `0`, `0abc`, `00` | 無効 |
| `1`, `10`, `true`, `false`, ` abc` | 有効 |

CLI の `--batch-mtp` が指定されていれば、環境変数が unset / 空 / `0` でも opt-in は有効です。設定が有効でも、後述の必要条件に合わなければ warning を出して機能を無効にします。

サーバーの案内ログ判定は engine と同一ではありません。`parallel > 8` のとき、CLI 引数に `--batch-mtp` がなく、環境値が `""` または `"0"` と完全一致する場合に最大8件の案内を表示します。たとえば `"00"` は server ではこの案内を抑えますが、engine では先頭が `0` のため MTP batch を無効にします。`STRATA_BATCH_MTP` 自体が `--batch N` を作ることはなく、server 設定の `parallel` か CLI の batch 指定が別途必要です。

## 有効になる条件

- `--serve` が必要です。
- `--batch` が2以上である必要があります。
- `--mtp` と `--spec T`（`T >= 2`）が必要です。
- CUDA engine は単一 GPU、または各 layer-split stage が別 GPU にある構成で動作します。同一 GPU 上に複数 stage がある split は不可です。layer split 上では slot drafter は最後の stage の GPU に置かれます。
- CUDA layer split では helper-GPU expert cache と `--remote-expert-opt` を使う構成は不可です。
- `--batch-groups` の解決結果が1 groupである必要があります。複数 group の pipelined slot path は MTP draft を実行しないため、engine は opt-in を無効にします。layer split で `--batch-groups` を省略した場合は、MTP が要求されると自動設定が1 groupを選びます。
- SYCL engine の現行実装は単一 GPU のみで、layer split / helper を含む構成では無効です。

条件を満たさない場合も通常の batch 起動は続けられます。stderr には `strata generate: WARNING: --batch-mtp is off: ...` と条件別の理由が出ます。batch 自体が成立しない場合は別途 `--batch ... is off` の warning が出ます。`--batch-mtp` が無効なら、engine は通常の batch window 上限（8 rows）に合わせて slot 数を調整します。有効時は各 active slot が2 rowsを使い、一 window あたり最大4 slotを処理し、より多い slot は順に window へ回します。

## 実行時の詳細

CUDA 実装 (`src/program/generate.cpp`) と SYCL 実装 (`sycl/src/program/generate.cpp`) は同じ起動時判定を行います。環境変数を実行中に変更しても、すでに決めた `batch_mtp` の状態は変わりません。設定が通ると各 batch slot 用の `MtpDrafter` を作り、最大 draft 数を1にします。CUDA では起動時に `--batch-mtp: N slot drafters on CUDA...` と slot ごとの private K/V state・buffer の容量、空き VRAM を stderr に出します。SYCL 側にも slot drafter と residual buffer の確保があります。

window は slot ごとに現在 token の row と proposal の row を組み立てて検証します。proposal がモデルの選んだ token と一致し、EOS・停止・出力上限・context 上限に抵触しない場合に限り、その slot の2 token分を commit します。採用されなければ通常の1 tokenだけを commit します。batch のサマリーには `strata batch: MTP proposals accepted ...` が出ます。slot ごとに drafter の K/V と buffer が必要なので、メモリ不足では確保・load のエラーで起動が失敗することがあります。

## 文書との照合

`docs/BATCHING.md` は server 環境での設定方法、1 slot あたり1 proposal、layer split での GPU 配置、group / helper 制約を説明しており、現行コードと概ね一致します。同文書は特定構成での測定として、2x RTX 3080 20 GB の layer split では serial batch window 比 +15.4%（測定条件は同文書に記載）、一方 2x R9700 で全 expert が VRAM に収まるケースでは pipelined default 比 -21.9% と報告しています。`docs/DETAILS.md` も後者の 80.2 → 62.7 tok/s を記載しています。これらは特定条件での `--batch-mtp` 機能全体の比較であり、この環境変数単独の性能測定や一般的な速度保証ではありません。

## 根拠

- `src/program/generate.cpp:4301-4337`: CUDA の値判定、適用条件、warning。
- `src/program/generate.cpp:4340-4350,4455-4477,7538-7565`: batch row 上限、slot drafter の作成とログ、verifier の設定。
- `src/program/generate.cpp:9337-9361,9413-9424,9541-9544`: 1 slot 2 row の window 構成、採用時 commit、集計ログ。
- `sycl/src/program/generate.cpp:3860-3885,3987-3999,7140-7172,8815-8839,8858-8868`: SYCL の判定、資源確保、window 処理。
- `serve/server.py:2372-2393`: `parallel` 設定と server 側の案内ログ判定。
- `docs/BATCHING.md:22-57,66,112-118,210-216`、`docs/DETAILS.md:1233`: 設定方法、測定条件、制約の照合。
