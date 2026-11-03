# `STRATA_PF_OWN_CHECK`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

Windows の HIP build で Strix Halo（gfx1151）の `--serve` を使う場合に、prompt path が自前の buffer を確保する際の事前 VRAM 算術チェックを有効に戻します。この環境変数は chunk 値を直接指定しません。要求された chunk が事前チェック上の空き容量に収まらない場合、通常はその結果で chunk を小さくします。gfx1151 用の既定設定ではこのチェック結果を理由に chunk を下げないため、その動作を戻す調査・試験用のスイッチです。

## 値と判定

読み取り時に `std::getenv()` の値が存在し、先頭文字が `'1'` なら有効です。文字列全体の比較や数値変換はしません。

| 値 | 判定 |
|---|---|
| 未設定 | 無効 |
| 空文字 | 無効（値は存在するが先頭文字が `\0`） |
| `1`, `10`, `1anything` | 有効 |
| `0`, `true`, `01`, ` 1` など | 無効 |

大文字小文字、空白、後続文字、数値としての妥当性は検査されません。無効な値でも警告やエラーにはなりません。判定は関数内の `static const bool` に保存され、最初の評価後に同じプロセス内で環境値を変更しても再評価されません。

## 有効になる条件

この値が処理に影響するのは、`o.prefill_own_keep_chunk` が true で、要求された chunk が `own_fits()` の算術チェックに収まらない場合です。この状態は HIP build の Windows で、GPU 0 が integrated、可視 GPU がすべて integrated かつ同じ gfx1151 系列であり、`STRATA_PREFILL_BORROW=1` でも `STRATA_GFX1151_DEFAULTS=0` でもない場合に設定されます。該当条件では Strata が自前 prompt buffer を使う設定にし、既に選ばれた chunk を保つ扱いにします。

| 条件 | `STRATA_PF_OWN_CHECK` の効果 |
|---|---|
| 上記 gfx1151 Windows HIP 条件外（CUDA、Linux HIP、他 GPU、または既定を無効化） | `o.prefill_own_keep_chunk` が false のため、この変数による差はありません。 |
| gfx1151 Windows HIP 条件内で算術チェックが通る | chunk は変わらず、この変数による差はありません。 |
| 同条件内で算術チェックが通らず、この変数が未設定または先頭文字が `1` 以外 | 「unified pool」の空き容量を理由にした事前の chunk 縮小を抑止し、現在の chunk を保ちます。 |
| 同条件内で算術チェックが通らず、この変数の先頭文字が `1` | 保持の例外を解除し、候補 chunk を小さい順に調べ、収まる最初の値へ下げます。 |

`STRATA_PREFILL_BORROW=1` は gfx1151 の自前 buffer 設定を抑止し、`STRATA_GFX1151_DEFAULTS=0` はその gfx1151 既定ブロックを無効にします。どちらの場合もこの変数だけでは設定状態を戻しません。`--prefill` 等で決まった `o.prefill_chunk` をこの環境変数が上書きすることはなく、事前チェックが失敗した際の保持または縮小を切り替えます。

## 実行時の詳細

サーバー起動時、prompt path 初期化の直前に、各 stage のうち buffer を借りていない経路について `Prefill::bytes_needed()` と `cudaMemGetInfo()` の空き容量を比較します。必要量に headroom（chunk が 512 以下なら 128 MiB、それより大きければ 512 MiB）を加えて空き容量を超えた場合、その chunk は事前チェック不適合です。候補は `6144, 4096, 3072, 2048, 1536, 1024, 512` token で、現在より小さく全対象経路に収まる最初の値を採用します。

gfx1151 の保持経路で算術チェックが不適合でも、この変数が無効なら `strata serve: a ...: kept (this GPU's memory is the unified pool; STRATA_PF_OWN_CHECK=1 steps the chunk down by that figure)` を stderr に出し、事前縮小を行いません。有効なら保持経路を外し、収まる候補があれば `strata serve: a ...: ...-token chunks` と出して `o.prefill_chunk` を更新します。収まる候補がなければ、この事前処理では chunk は更新されません。

実際の prompt path 初期化に失敗した場合は別の回復経路があります。戻り値が `2`（buffer 不適合）で、より小さい候補が残っていれば、環境変数の値にかかわらず候補へ下げて初期化をやり直し、`strata serve: ...: trying a ...-token chunk` を出します。再試行できない失敗はエラーを stderr に出して終了コード `1`、起動時の `--serve` / `--spec` / `--prefill` 等の前提不足は終了コード `2` になります。

## 根拠

- `src/program/generate.cpp:10054-10059` — `--serve` 経路と起動時の前提検査。
- `src/program/generate.cpp:3702-3719,3720-3724,3746-3760` — HIP 限定の gfx1151 検出、Windows / UMA 条件、`STRATA_PREFILL_BORROW` と `STRATA_GFX1151_DEFAULTS` による有効化条件。
- `src/program/generate.cpp:10652-10672` — chunk 候補、headroom、借用していない prompt path の空き容量判定。
- `src/program/generate.cpp:10676-10703` — 環境変数の読み取り・static cache、事前縮小の保持分岐とログ。
- `src/program/generate.cpp:10705-10742` — prompt path 初期化失敗時の縮小再試行、エラー出力と終了。
