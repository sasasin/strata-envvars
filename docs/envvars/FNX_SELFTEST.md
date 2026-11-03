# `FNX_SELFTEST`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

HIP 版の all-cards split engine が起動時に行う GPU kernel self-test を、通常は試験済みの `gfx1201` でも実行するための opt-in です。対象アーキテクチャが未試験ならこの変数に関係なく self-test を実行します。CUDA 版では読み取り箇所がありません。

## 値と判定

値は `std::strcmp(value, "1") == 0` で文字列全体を比較します。数値変換や trim、大文字小文字変換はありません。

| 先頭 GPU のアーキテクチャ | unset | 値が厳密に `1` | その他（空文字を含む） |
|---|---|---|---|
| `gfx1201` で始まる | self-test を省略 | self-test を実行 | self-test を省略 |
| それ以外 | self-test を実行 | self-test を実行 | self-test を実行 |

`1 `、`01`、`true` などは `1` と一致せず、`gfx1201` では self-test を有効にしません。未設定と空文字も opt-in ではありません。`FNX_SELFTEST_FAIL` は別変数であり、self-test が選択された経路でのみ失敗を強制します。

## 有効になる条件

- `src/split/src/model.cpp` の `check_cards()` 内で、この処理は `#if FNX_HIP` の範囲にあります。従って HIP ビルドだけが対象です。
- all-cards split engine のモデル初期化で `check_cards()` に到達したとき評価されます。通常の Strata layer-split 経路ではこの engine の判定は走りません。
- 判定に使うのは GPU 0 の `gcnArchName` です。self-test が選ばれた場合は callback が `NCARD` 台すべてに対して `selftest_card()` を実行します。
- `FNX_SELFTEST` の判定値をキャッシュする `static` はありません。環境値は `Model` 初期化時の `check_cards()` 呼び出しで読み取られ、モデル初期化後に値を変えてもその実行済み判定はやり直されません。CLI 引数や設定ファイルによる上書き処理はこの判定にありません。

## 実行時の詳細

self-test は `Model` 構築中の `check_cards()` で実行され、カード確認の後に `check_supported()` などのモデル処理へ進みます。全 GPU について WMMA operand layout、expert tile、dense product、dp4a、recurrent step の順に検査し、最初の失敗で打ち切ります。これらのテストが失敗した場合、または `FNX_SELFTEST_FAIL=1` によって失敗を強制した場合、engine は stderr に失敗行を出して例外で起動を拒否します。server 経由では all-cards engine の起動失敗を捕捉し、通常の layer split を起動します。

self-test を実行した場合の stderr 行は `fnx: The split engine's self-test passed on <arch> (<covered>).` または `fnx: The split engine's self-test failed on <arch> (<reason>), so it does not run on this card: the normal layer split starts instead.` です。未試験アーキテクチャでは、その前に未試験であることと報告先を示す `fnx:` 行も出ます。判定を省略した `gfx1201` では self-test の pass/fail 行は出ません。

## 根拠

- `src/split/src/hip/selftest_policy.hpp:21-22,31-50` — 試験済みアーキテクチャの判定、値の厳密比較、未試験カードでの常時実行、ログ内容と失敗判定。
- `src/split/src/model.cpp:100,129-146` — HIP 条件、GPU 0 のアーキテクチャ取得、環境値の読み取り、全 GPU への self-test 呼び出し、stderr 出力と例外。
- `src/split/src/model.cpp:1253-1266` — モデル構築時にカード確認を行い、その後のモデル検査へ進む順序。
- `src/split/src/selftest.cu:306-322` — 1 GPU あたりの検査一覧、最初の失敗での終了と pass 時の covered 表記。
- `serve/server.py:9107-9145` — server が engine の起動失敗を捕捉し、fallback 設定がある場合に通常の layer-split engine を起動する処理。
