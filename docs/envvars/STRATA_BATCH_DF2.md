# `STRATA_BATCH_DF2`

調査対象: Strata `main` の HEAD `9f7d977d220e9fdf2ec53cf2620cdadac1cfb24e`（2026-11-06 時点）。

## 役割

`strata generate --serve` の `--batch` スロットでも、各スロットに DFlash2 drafter を割り当てるかを制御します。明示的な `--draft dflash2` と `--batch N`（`N >= 2`）を指定した場合、既定では適用条件を満たす構成でスロットの DFlash2 draft が有効になります。この変数はその既定選択を止めるか、通常は適用されない構成でも要求するためのスイッチです。単独の `--draft dflash2` や `--draft auto` の選択を変える変数ではありません。判定と `--batch-mtp` の共通ゲートは `src/program/generate.cpp:6766-6809` にあります。

## 値と判定

文字列を数値や真偽値として parse せず、先頭文字だけを見ます。

| 値 | `batch_df2_wanted` の判定 |
|---|---|
| 未設定 | 通常の適用条件による自動判定 |
| 空文字 | 未設定と同じ自動判定 |
| 先頭が `0`（例: `0`, `0anything`） | OFF |
| 非空で先頭が `0` 以外（例: `1`, `true`, `false`, `2`, `anything`） | 強制要求 |

空白も含め、数値妥当性・文字列全体・大文字小文字は検査されません。したがって `false` も強制要求です。Metal ビルドでは値にかかわらず判定結果を `false` にします。根拠: `src/program/generate.cpp:6772-6783`。

## 有効になる条件

有効値の判定だけでは slot drafter は起動しません。次の基本条件を満たす必要があります。

- `--draft dflash2` が明示され、`--draft auto` ではない。
- `--batch` が 2 以上で、`--serve` を使う。
- 同一 GPU に重なる layer split（`split_same`）ではない。
- `--spec` が 2 以上である。
- DFlash2 を使えるビルドとモデル・pack があり、solo DFlash2 drafter が起動すること。

このうち `--batch`、`--serve`、`--spec`、layer split の制約は batch MTP 共通ゲートで検査され、満たさない場合は警告を出して batch draft を無効にします。layer split では helper GPU expert cache がある構成も共通ゲートで除外されます。根拠: `src/program/generate.cpp:6785-6809`。

値が未設定または空文字のとき、単一 GPU では上記の基本条件を満たせば既定で有効です。layer split では、スロットが一つの group で実行される場合だけ既定で有効になります。非空の値（先頭 `0` 以外）で強制要求すると、この group 数による自動判定を通過しますが、共通ゲートが別途適用されます。pipelined group のスロットは DFlash2 draft を持たない設計であり、group 構成により共通ゲートが batch drafting を無効にする場合もあります。根拠: `src/program/generate.cpp:6779-6783,6793-6809`。

DFlash2 drafter 自体は `--pipeline-windows` と併用できず、DFlash2 が起動しなければ batch DFlash2 も使えません。Metal は per-slot drafter の clone に対応しないため常に無効です。CMake では DFlash2 実装を CUDA/HIP ビルドで有効にし、Metal/SYCL ビルドでは含めないとしています。根拠: `src/program/generate.cpp:6987-6995,7102-7108,7157-7179`、`CMakeLists.txt:434-441`。

## 実行時の詳細

環境変数は `generate.cpp` の serve/batch 初期化中、`batch_df2_wanted` を作るときに一度 `std::getenv` で読みます。static cache はありませんが、この結果は `const bool` として後続の初期化で使われるため、起動後に環境を変更しても再判定されません。通常は共通 gate を通過し、solo DFlash2 の load が成功すると、各 batch slot 用に pack を共有する drafter clone を確保し、それぞれに個別の K/V ring と buffer を持たせます。確保失敗は slot 番号と理由を stderr に出して起動を失敗させます。根拠: `src/program/generate.cpp:6772-6784,7157-7173`。

batch window では各 active slot にまず token の行を割り当て、余った行を DFlash2 draft に分配します。余剰行がない round は drafter を回さず、後で必要になった時点で遅延分を追いつかせます。draft 行数は `STRATA_BATCH_DF2_MAXX`、信頼度しきい値は `STRATA_BATCH_DF2_CONF`（未設定・空なら `--draft-conf` が正、さもなくば 0.35）でも制限されます。`STRATA_BATCH_DF2_DEFER=0` は余剰行がない round も毎回 draft を行う動作を選びます。これらは本変数とは別の調整値です。根拠: `src/program/generate.cpp:13990-13996,14273-14300,14475-14504`。

`--batch-mtp` または `STRATA_BATCH_MTP` は batch draft 共通ゲートを別途要求しますが、`STRATA_BATCH_DF2=0` は DFlash2 slot drafter のみを止めます。DFlash2 が OFF でも MTP fallback があれば batch MTP が動く経路があります。逆に DFlash2 を要求したのに solo DFlash2 が起動しなければ `STRATA_BATCH_DF2 is off: DFlash2 is not running` の警告を出し、slot draft を無効にします。根拠: `src/program/generate.cpp:6785-6809,7157-7177`。

実行中の主な観測結果は、初期化成功時の `STRATA_BATCH_DF2: N slot drafters on CUDA…` と serve 準備完了時の `STRATA_BATCH_DF2: N slot drafters ready ...` です。solo DFlash2 が失敗して fallback する場合や gate 条件を満たさない場合は stderr に警告が出ます。slot drafter の `clone_bind` / `prepare` が失敗すると `strata serve: STRATA_BATCH_DF2: slot N: ...` を出して serve 初期化を終了します。batch window 内の DFlash2 処理失敗は `ERR batch DFlash2 slot N: ...` を出して処理を失敗させます。根拠: `src/program/generate.cpp:6806-6809,7171-7176,11576-11588,14475-14504`。

## 根拠

- 判定値・適用条件: `src/program/generate.cpp:6772-6809`
- DFlash2 compile 条件・ロードと per-slot clone の確保: `CMakeLists.txt:434-441`, `src/program/generate.cpp:6987-6995,7102-7108,7157-7179`
- slot drafter の bind/prepare と serve 起動失敗: `src/program/generate.cpp:11576-11588`
- batch window の draft 行割当・遅延処理・失敗経路: `src/program/generate.cpp:14273-14315,14475-14504`
- 調査対象 checkout には本変数の batch DFlash2 挙動を説明する設計資料は見つかりませんでした。`docs/DETAILS.md` 等の DFlash2 一般説明や他用途の測定値は、本変数の効果の根拠として転記していません。
