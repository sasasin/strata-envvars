# `STRATA_ADAPT_OVERLAP`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリの環境変数は対象外。

## 役割

適応層（adaptive tier）が GPU に送る expert の入れ替えコピーを、次の decode window の実行と重ねます。通常はコピー完了を待ってから residency table を更新します。この機能では、通常ならその待ちが終わる時点で residency table を先に更新し、コピーは layer 順に続けます。検証 window は、入れ替えのある layer について、その layer のコピーが到着するまで GPU の実行計画を進めません。したがって、GPU/CPU で計算する expert の選択と生成 token は通常の待機方式と同じで、変わるのはコピー待ちの配置です。

実装は `src/program/generate.cpp` の `adapt_overlap()` と decode loop、`include/strata/core/verify.hpp` の `AdaptGate`、`src/core/verify.cpp` の layer gate にあります。環境変数の判定結果は関数内の `static const bool` に保存されます。プロセス内で最初に判定した後、実行中に環境を書き換えても再評価されません。

## 値と判定

実装は文字列全体を parse しません。`getenv()` の結果の先頭文字 `e[0]` だけを比較します。空文字は値が設定されている状態ですが、先頭文字は `\0` です。

| ビルド | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| Linux CUDA | 有効（既定） | 先頭文字が `0` ではないすべての文字列。例: `1`, `true`, `false`, `2`, 空文字 | 先頭文字が `0` の文字列。例: `0`, `0anything` |
| Windows CUDA | 無効 | 先頭文字が `1` の文字列。例: `1`, `10`, `1anything` | それ以外すべて（unset、`0`, `true`, 空文字を含む） |
| HIP | 無効 | 先頭文字が `1` の文字列。例: `1`, `10`, `1anything` | それ以外すべて（unset、`0`, `true`, 空文字を含む） |

大文字小文字、空白、数値としての妥当性は検査されません。たとえば Linux CUDA では `false` も有効、Windows CUDA/HIP では `true` は無効です。`STRATA_ADAPT_OVERLAP=0` はすべてのビルドで無効にします。

根拠: `src/program/generate.cpp:1335-1347`。

## 有効になる条件

上の値判定が有効でも、次の条件をすべて満たさなければ overlap 動作は有効化されません。

- 適応層が稼働している（`--adapt-every` と `--adapt-swaps` による usage table が空でない）。
- 単一 GPU で、layer split / 複数 GPU ではない。
- `--peer-device` と `--remote-expert-opt` を使っていない。
- `--adapt-async` と `--pipeline-windows` を使っていない。
- page-locked swap source が無効。
- `STRATA_DMA_BATCH` が無効（DMA batch mode が 0）。
- `STRATA_ADAPT_LAG` が既定値の 1 で、`STRATA_ADAPT_NOWAIT` が有効でない。
- `STRATA_VERIFY_DEVICE_PLAN` による device-planned layers が有効でない（Verifier が gate の設定を拒否する）。
- resident RAM mode（`src.complement_ready()`）では、別の環境変数 `STRATA_ADAPT_OVERLAP_RESIDENT` の先頭文字が `1` である。

条件を満たさないとき、要求値が環境変数に明示設定されていれば stderr に `STRATA_ADAPT_OVERLAP=1 is off: ...` と理由を出します。Linux CUDA で変数を unset のまま既定 ON にした場合は、条件に合わなくてもこの理由ログは抑制されます。条件を満たして開始した場合は `adaptive overlap ...` の有効ログが出ます。

resident RAM mode では別変数を `1` にしても常に overlap できるとは限りません。swap のソフト commit に失敗した場合、実装は通常のコピー完了待ちに fallback します。関連箇所: `src/program/generate.cpp:8277-8304,11861-11870`。

## 実行時の詳細

コピー完了を通知する CUDA stream host callback が、各 layer の最後の swap の後に `AdaptGate::landed` を更新します。Verifier はその layer の GPU 処理が到達した後、swap のある layer なら `landed >= layer` になるまで spin wait し、それから layer の計画を公開します。all-resident graph の経路では layer ごとに止められないため、graph の launch 前にすべてのコピーを待ちます。gate wait は 20 秒を超えると window error になります。

参照: `src/program/generate.cpp:8448-8459`, `include/strata/core/verify.hpp:46-53`, `src/core/verify.cpp:2120-2134,2169-2172,2235-2237`。

## ログと測定値

この最適化は同じ token を生成する設計です。Strata の `docs/DETAILS.md` は Linux CUDA では既定 ON、Windows CUDA/HIP では opt-in と説明しています。記載された測定では RTX A4000 の 6 組の interleaved run で、decode median tok/s が Q2_0 16 GB 62.5→66.2 (+5.9%)、Q2_0 12 GB 51.3→54.2 (+5.7%)、IQ3_XXS 16 GB 48.6→52.6 (+8.3%)、IQ3_XXS 12 GB 39.3→41.5 (+5.5%) で、各条件とも 6/6 組で向上しています。これは記載された測定環境での値であり、他機種の性能を保証しません。Windows RTX 5070 の Q2_0 では -2.6%、IQ3_XXS では中立だったため Windows は既定 OFF、HIP は未測定で opt-in です。

出典: `docs/DETAILS.md:1699-1706`。実装注釈には Linux CUDA の別測定として A4000 +5.5–8.3%、P100 +4.4% とあります（`src/program/generate.cpp:1333-1344`）。
