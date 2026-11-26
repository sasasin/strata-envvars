# `--family`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `setup.py` / `setup.sh` / `START-HERE.bat`（root） |
| オプション | `--family` |
| 別名 | なし |
| 値 | family ID 文字列。root parser の組み込み候補は `qwen`、`swift`、`coder`、`unsloth`、`gyro`、`nvfp4`、`qwen36`、`hy4-flash`、`inkling-2-mini`。署名済み update feed にモデル定義がある場合は追加候補が動的に読み込まれる。 |

## 役割

導入・設定するモデル群を選び、family に対応したモデル一覧、ファイル定義、セットアップ経路を決める。省略時は対話メニューで選択する。指定した場合も通常 family では `--model` を省略でき、その family のサイズ選択に進む。`--model` と併用すると、family とサイズの組み合わせを検証する。

## 使い方

```bash
# Qwen family の IQ3_S を導入し、モデル起動は行わない。モデル等の取得・準備と設定書き込みは行う。
./setup.sh --family qwen --model IQ3_S --yes --no-start
```

`setup.sh` は引数を `terminal/setup.py` に転送する。Windows の `START-HERE.bat` も同様に `setup.py` を起動する。Apple Silicon の通常モデル導入は `engine/metal/setup_mac.py` に委譲され、その parser は別スコープのためこの文書の対象外（`setup.sh:8-17`、`START-HERE.bat:8-17,49-65`、`terminal/setup.py:11436-11437`）。

## 値と既定値

- root parser は `FAMILIES`、`PREVIEW_FAMILIES`、`HY4_FAMILIES`、`INKLING_FAMILIES` のキーを `choices` として受理する。現行の組み込みキーはそれぞれ通常 family が `qwen` / `swift` / `coder` / `unsloth` / `gyro` / `nvfp4`、独自 engine path が `qwen36`、個別 engine family が `hy4-flash` と `inkling-2-mini`（`terminal/setup.py:723-775,789-812,818-832,11444-11448`）。
- 未指定時に parser が入れる family 既定値はない。導入メニューを出す経路では family を対話選択する。`--yes` を指定しても family の固定値は設定されず、tier と候補に基づく推奨 family が選ばれる（`terminal/setup.py:11988-12018`）。
- 初回の引数確認で組み込み表にない family が見つかると、署名済み feed のモデル一覧（または最後に検証済みの一覧）を読み込み、候補表を更新してから argparse を構築する。このため受理候補は checkout 内の固定リストだけでは完結しない（`terminal/setup.py:11438-11448,9645-9647,9677-9692`）。
- 値なし、未登録の family、または parser の候補に入らなかった値は argparse の選択肢検証で拒否される。`--family` を付けた状態でサイズがその family に属さない場合も、利用可能なサイズを示して失敗する（`terminal/setup.py:11445-11448,12046-12054`）。

## 実行時の動作

family が明示されると対話の family 選択を省き、その値で分岐する。`qwen36` は `install_own_path`、`hy4-flash` は `install_hy4_flash`、`inkling-2-mini` は `install_inkling2` へ入り、その他は `FAMILIES[family]` の定義を使う通常のセットアップ経路に進む（`terminal/setup.py:11993-12025`）。通常経路では family に属するモデル候補だけを表示・検証し、family 定義から対応するファイルや設定を決める（`terminal/setup.py:723-775,12046-12055`）。

`--model` を併記するとそのサイズを選び、family に属さないサイズなら family 名・有効サイズを含むエラーになる。`--gguf-dir` の GGUF ファイル名から family と model の組み合わせが一意に特定できる場合は、`--family` を省略しても値が補われる（`terminal/setup.py:11983-11987,12046-12054`）。

## 適用条件と副作用

- `--check`、`--prepare-pack`、`--inspect` など先行する別モードは通常のモデル導入分岐より前に処理されるため、その経路では `--family` が通常のモデル導入を開始するわけではない（`terminal/setup.py:11624-11638,11775-11779`）。
- root parser の `--family` 候補の事前確認では、組み込み表にない名前に対して feed を取得できる設定なら feed を読み込む。feed source が得られない場合は最後に検証済みのモデル一覧を使う（`terminal/setup.py:11438-11444,9677-9692`）。
- family の選択後に進む導入処理は、モデルファイル取得・検証、モデル準備、エンジンや実行設定の用意を行い得る。`--no-start` は導入後のモデル起動を抑えるが、これらの導入処理を取り消さない（通常 family の選択・モデル導入開始: `terminal/setup.py:12019-12025,12046-12055`）。
- DeepSeek の退役 family 名は parser に到達する前に案内を表示して終了コード `2` で終了する。`--model` だけが退役名の場合も条件により同様に拒否する（`terminal/setup.py:11429-11433`）。
- `engine/metal/setup_mac.py` は `--family` の別 parser を持ち、Mac では `qwen` / `unsloth` / `gyro` と feed family を受け付ける。Mac parser は不明な残余引数も警告して続行する。この挙動は root parser の検証と異なる（`engine/metal/setup_mac.py:361-379,403-410`）。

## 出力とエラー

標準の argparse により無効な候補は usage と選択肢エラーになり、終了コードは argparse の通常のエラー経路に従う。退役 family は独自メッセージを表示して `2` を返す。Intel Arc 経路で通常 family が SYCL engine に対応しない場合は family 選択後に失敗する（`terminal/setup.py:11429-11448,9378-9382`）。family と model の不一致は候補 family と有効サイズを含むセットアップエラーになる（`terminal/setup.py:12046-12054`）。

## 根拠

- `terminal/setup.py:11427-11448` — 早期の family 確認、動的 feed 読み込み条件、root parser の `choices`。
- `terminal/setup.py:723-832` — 組み込み family 定義と独自導入経路 family。
- `terminal/setup.py:9645-9692` — feed family 表と署名済み feed モデルの読み込み。
- `terminal/setup.py:11619-11638` — model/family の初期検証とモード分岐。
- `terminal/setup.py:11983-12025` — `--gguf-dir` からの補完、対話選択、family 別の導入関数への分岐。
- `terminal/setup.py:12046-12055` — family に属する model サイズの候補化と不一致エラー。
- `terminal/setup.py:9363-9382` — SYCL 経路での family 既定値と対応可否検証。
- `setup.sh:8-17`、`START-HERE.bat:8-17,49-65` — POSIX / Windows wrapper から `setup.py` への引数転送。
- `engine/metal/setup_mac.py:361-410` — Mac 用の別 parser と引数処理。

調査範囲は Strata 所有ソースの root setup parser、family 表、選択・分岐処理、および Mac 委譲境界。調査中に CLI を実行しておらず、feed の実行時内容は確認していないため、動的な feed family 名は列挙していない。
