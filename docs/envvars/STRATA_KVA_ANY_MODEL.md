# `STRATA_KVA_ANY_MODEL`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

KVA（近似 prompt prefill）が測定対象として扱う形状は 48 層・512 experts です。この変数を有効にすると、その形状以外でも、他の KVA 適用条件を満たした cold prefill で近似経路を許可します。形状チェックを飛ばす研究用 override であり、KVA 自体を有効化する設定ではありません。KVA の opt-in `STRATA_KVA` が有効でない場合や KVA 経路が別の理由で拒否される場合、この変数だけでは近似読み取りは行われません。判定は `engine/include/strata/prefill/kva.hpp:51-52,108-133,143-162`、形状を渡す箇所は `engine/src/prefill/prefill.cpp:4227-4244` です。

## 値と判定

`kva_env_flag("STRATA_KVA_ANY_MODEL", false)` が `std::getenv` で取得します。未設定または空文字なら既定値 `false`。それ以外は先頭 1 文字だけを見て、`'0'` 以外なら `true` です。値全体の parse、数値妥当性検査、空白除去、大文字小文字変換はありません。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| KVA 設定の読み取り | `false` | 空でない文字列の先頭が `0` 以外（例: `1`, `true`, `yes`, ` 1`, `2junk`） | 空文字、または先頭が `0`（例: `0`, `0anything`） |
| KVA build backend が無効（Metal） | `false` | フラグ自体は同じ規則で parse されるが、KVA の `on` は backend 判定で無効化される | 同左 |

対象変数に CLI 引数や別の値による上書きはありません。設定有無だけを見る判定ではなく、空文字は明示設定として扱われません。根拠: `engine/include/strata/prefill/kva.hpp:43-49,143-146,152-162`。

## 有効になる条件

- `STRATA_KVA` も有効であること。KVA は未設定・空文字・先頭文字が `0` の場合は off で、`STRATA_KVA_ANY_MODEL` が有効でも単独では作動しません。`engine/include/strata/prefill/kva.hpp:77-84,152-162`。
- KVA 実装経路を含む build であること。`STRATA_GPU_METAL` が定義された build では `kKvaBackend` が false となり、`STRATA_KVA` の `on` も false にされます。`engine/include/strata/prefill/kva.hpp:43-49,152-156`。Metal では `STRATA_KVA` が明示的に有効な場合、起動時に「`strata generate: STRATA_KVA is set, but this build has no state-only late-layer path; every prompt is read exactly`」と stderr に出ます。`STRATA_KVA_ANY_MODEL` 単独ではこのログ条件になりません。`engine/src/program/generate.cpp:8099-8105`。
- 対象が 48 層または 512 experts のいずれかと異なる場合に、この変数の override が効きます。48 層かつ 512 experts なら変数の値に関係なく形状ゲートは通ります。`engine/src/prefill/prefill.cpp:4233-4235`。
- 形状ゲートより前にある KVA 条件も満たす必要があります。capture 中でないこと、engine 全体が batch slots・GPU 間 layer split・peer GPU でブロックされていないこと、prompt が position 0 から始まること、layer split でないこと、画像 prompt でも DFlash2 の tap でもないこと、`STRATA_KVA_MIN_PROMPT` 以上であること、かつ有効 suffix に 64 token を加えた数より prompt が長いことが必要です。条件は順に評価され、先に該当した理由で拒否されます。`engine/include/strata/prefill/kva.hpp:108-133`。batch slots・layer split・peer device の process-wide block は `engine/src/program/generate.cpp:8105-8114` で設定されます。
- この変数は KVA の開始層、suffix、KVA が変更する層や計算内容を変えません。それらは `STRATA_KVA_SPLIT`、`STRATA_KVA_SUFFIX`、`STRATA_KVA_ONLY`、`STRATA_KVA_SKIP` など別の設定によります。`engine/include/strata/prefill/kva.hpp:83-96,157-188`。

## 実行時の詳細

通常の実行経路は `kva_config()` の関数内 `static const KvaConfig` を初回に構築し、その中で対象変数を一度読みます。従ってプロセス起動後に環境を変更しても、この設定には反映されません。テストや他の明示的な呼び出しで使われる `kva_config_from_env()` 自体は毎回読み直しますが、実行時の prefill は cache 済み `kva_config()` を使います。`engine/include/strata/prefill/kva.hpp:149-162,191-195`、利用側 `engine/src/prefill/prefill.cpp:4227-4235`。

変数が有効で、KVA opt-in と他の判定を通ると、48/512 以外の形状でも `decline()` が形状理由で拒否しなくなります。prefill 側はそのモデルの層数・expert 数を比較して警告をプロセス内一度だけ stderr に出し、KVA chunk 経路に進みます。chunk が近似対象になると `kva_run` により split 以降の対象層の state-only（または別設定の MoE skip）処理が選択されます。`engine/src/prefill/prefill.cpp:4233-4249,4405-4412,4680-4692,4997-5007`。

## ログと測定値

形状が標準外でも他の条件を通過したときの警告は stderr に一度だけ出ます（文言は実装どおり）。

```text
strata prefill: WARNING: STRATA_KVA_ANY_MODEL=1: KVA was only measured on Qwen3.8-Flash-Next (48 layers, 512 experts); this model has %lld layers and %lld experts
```

KVA が `STRATA_KVA=1` で有効だが形状ゲートで拒否される場合は、対象変数が無効なら stderr に次の理由行が出ます。対象変数が有効なら形状拒否を通過して上記警告の条件になります。どちらの行も、KVA が off の場合にはこの形状分岐からは出ません。`engine/src/prefill/prefill.cpp:4236-4243,8032-8044`。

```text
strata prefill: KVA configured but NOT applied: this model's shape (%lld layers, %lld experts) is not one KVA was measured on (STRATA_KVA_ANY_MODEL=1 allows it)
```

## 根拠

- `engine/include/strata/prefill/kva.hpp:43-49,51-52,108-146,149-195` — backend 判定、shape gate、flag parser、設定の cache。
- `engine/src/program/generate.cpp:8093-8115` — KVA build 条件、batch/layer split/peer GPU の block と起動ログ。
- `engine/src/prefill/prefill.cpp:4227-4249,4405-4412,4680-4692,4997-5007,8032-8044` — 形状の判定・警告・近似 chunk 経路・拒否ログ。
- `docs/KVA.md:43-58,99-104,106-110` — 設計資料も、測定形状を外れる場合は既定で拒否し、研究用 `STRATA_KVA_ANY_MODEL=1` で警告付き許可する説明。挙動の根拠は上記ソース。
