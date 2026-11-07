# `STRATA_MANIFEST`

調査対象: Strata `main` の HEAD `146df3c468739147f520ac3816de806f71232571`（2026-11-07 時点）。

## 役割

診断用 JSON ファイルの出力先を指定します。この変数自体は engine の選択や計算経路を変更しません。通常 engine では選択された engine・予算・path 判定・tensor 形式を記録し、Python の all-cards split engine 判定では起動時の engine 選択理由を別ファイルに記録します。未設定時はどちらも記録しません。根拠: `include/strata/core/run_manifest.hpp:1-18,185-194`、`strata_control/split_engine.py:505-527`。

## 値と判定

値は boolean や数値として parse されず、ファイルパス文字列として使われます。両実装とも未設定と空文字列を無効とし、空でない文字列を出力先の基点にします。前後空白の除去、パスの正規化、値の検証、既定パスへの fallback はありません。CLI 引数や他の環境変数との優先順位もありません。根拠: `include/strata/core/run_manifest.hpp:43-47,185-194`、`strata_control/split_engine.py:505-524`。

| 値 | 通常 engine（C++） | split engine 判定（Python） |
|---|---|---|
| 未設定 | 無効 | 無効 |
| 空文字列 | 無効 | 無効 |
| 空でない文字列 `P` | `P` に manifest JSON を出力 | `P.launch.json` に起動判定 JSON を出力 |

## 有効になる条件

- C++ 側は `strata::core::manifest::enabled()` が真となる場所だけが記録します。通常 engine の初期化後、READY 前に engine 情報・予算と path 判定を記録し、dense/head tensor の形式・サイズ、prefill expert 経路なども該当する実装経路で追加します。CUDA/HIP 等の特定条件をこの環境変数が直接判定する処理はなく、記録対象コードが実行された場合にだけ項目が入ります。根拠: `src/program/generate.cpp:13897-13924,13992`、`src/core/native_dense.cpp:433-445,567-568`、`src/core/native_head.cpp:111-119`、`src/prefill/prefill.cpp:1529-1534,1565-1578`。
- Python 側は split engine の `apply_to_config()` が off 以外の mode で判定を行い、結果を記録するときに読みます。`apply_run_config()` が `deepseek41`、off、または必要な draft layer 不在で早期 return する場合はこの記録処理に到達しません。auto 判定が split engine を選ばなかった場合も、判定処理が完了すれば選択結果と理由を記録します。根拠: `strata_control/split_engine.py:479-493,669-693`。

## 実行時の詳細

C++ のプロセス共有 `Manifest` は `instance()` の関数内 static として初めて呼ばれた時に `getenv("STRATA_MANIFEST")` を評価し、そのパスを保持します。したがって、そのプロセス内では後から環境値を変えても反映されません。未設定時は空文字列を保持し、記録・書き込み関数は no-op になります。根拠: `include/strata/core/run_manifest.hpp:41-47,117-153,185-194`。

C++ 側では READY 時に `write("ready")` を呼び、request loop では前回書き出し後に記録内容が変わっていれば `flush_if_dirty("request")` で更新します。JSON には `manifest_version`、stage、engine、budgets、paths、tensors が入り、map の順序でキーが並びます。書き込みは `P.tmp` に行ってから `P` に rename します。書けない場合は stderr に `strata: STRATA_MANIFEST: cannot write <path>` を一度出し、呼び出し側は戻り値を使って停止させないため、実行は続きます。根拠: `include/strata/core/run_manifest.hpp:84-114,117-153`、`src/program/generate.cpp:13992,15323-15325`。

Python 側は split 判定のたびに `os.environ.get()`（テスト用 `environ` が渡された場合はその辞書）を参照します。`P.launch.json.tmp` に JSON を書いて `os.replace()` で `P.launch.json` に置き換えます。記録内容は mode、選択 engine、理由、カード・architecture、routed types、untested 条件、必要 VRAM/RAM、AMD auto rule です。例外はすべて捕捉され、関数は `False` を返すだけで起動判定を変更せず、警告ログも出しません。根拠: `strata_control/split_engine.py:505-527`。

## 根拠

- C++ の値読み取りと cache: `include/strata/core/run_manifest.hpp:41-47,185-194`。
- C++ の JSON 形式、ファイル更新、失敗時警告: `include/strata/core/run_manifest.hpp:84-153`。
- 通常 engine の記録内容と READY/request の書き出し時点: `src/program/generate.cpp:13897-13924,13992,15323-15325`。
- 読み込まれた tensor / prefill 経路の追加記録: `src/core/native_dense.cpp:433-445,567-568`、`src/core/native_head.cpp:111-119`、`src/prefill/prefill.cpp:1529-1534,1565-1578`。
- Python split engine 側の判定呼び出し、対象ファイル、失敗処理: `strata_control/split_engine.py:479-493,505-527,669-693`。
