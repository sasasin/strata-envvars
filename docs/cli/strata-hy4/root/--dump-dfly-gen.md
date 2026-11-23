# `strata-hy4 --dump-dfly-gen`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4`（トップレベル） |
| オプション | `--dump-dfly-gen` |
| 別名 | なし |
| 値 | 整数として `atoi` で変換。ソース上の範囲検証なし |

## 役割

`--dump-dfly-batch` で指定したトークン ID マニフェストの各プロンプトについて、DFly 用の系列ダンプを作る際の生成上限を指定する。単独ではダンプ処理を有効にせず、バッチ指定があるときに使われる。省略時の上限は 384 トークン。

## 使い方

```sh
# prompts.txt を入力し、新しい出力ディレクトリへ各系列を最大 64 トークン生成して保存する
strata-hy4 --model model.strata --dump-dfly-batch prompts.txt \
  --dump-dfly-gen 64 --dump-dfly-out ./dfly-dump-new
```

出力先には `seq_0000.bin` などのファイルが作られ、同名ファイルがあれば `wb` で上書きされる。既存データを残す場合は新しいディレクトリを指定すること。

## 値と既定値

- 値は `atoi` で整数に変換される。省略時は `384`。
- parser に範囲検証はない。先頭に数値がない値は `atoi` により `0` になり、数値部分の後ろに続く文字列も検証されない。負数もそのまま後段へ渡る。重複指定は引数走査中に都度代入されるため、最後の指定が残る。
- バッチ処理では各プロンプトの生成上限を `T0 + gen_n` として計算し、実際の系列長はコンテキスト上限と EOS によってさらに短くなり得る。上限以下のトークンを追加できない場合、そのプロンプトは系列ファイルを作らず次へ進む。
- `--ctx` が 0 以下または未指定の場合、`--tokens` から非空のトークン列を読み込んでいれば先にその長さ + `--gen` + 16 が自動値として設定される。それ以外ではバッチ指定時に `--dump-dfly-gen` + 512 が自動値になる。正の `--ctx` を指定すると、いずれの自動設定も使われない。

## 実行時の動作

引数走査では `--dump-dfly-gen VALUE` を `dump_dfly_gen` に代入するだけである。`--dump-dfly-batch` が指定されると、モデル初期化後にバッチ処理へ分岐し、この値を生成上限として渡す。バッチがない場合はこの値を使う分岐がなく、通常の `--gen` による生成数とは別の設定である。

各マニフェスト行は空行と `#` で始まる行を飛ばし、空白・タブ・カンマ・CR 区切りで整数トークン ID を読み取る。8 個以上の ID がある行だけがプロンプトとして採用される。長すぎるプロンプトは Runner の `Tc` まで切り詰められる。上限は採用プロンプトごとに適用され、EOS (`r.c.eos` または ID `120008`) が出ると早期終了する。生成時は `--dump-dfly-temp` と `--seed` も使われる。温度が負なら 3 系列中 2 系列を greedy、1 系列を絶対値の温度で sampling し、温度 0 以下は greedy、正の温度は sampling。seed が 0 の場合は処理内の固定 seed `20261120` が使われる。

生成された系列は `seq_%04zu.bin` として出力ディレクトリに保存される。出力先は `--dump-dfly-out` が空でなければその値、そうでなければ `--out`（既定値 `.`）。ディレクトリは作成され、ファイルはバイナリ書き込みモードで開かれる。出力にはヘッダー、トークン列、hidden state、KV データ、top-64 の token ID と log probability、tail probability が含まれる。

## 適用条件と副作用

- CUDA/HIP 用 `strata-hy4` のトップレベル引数である。索引上の parser 所在は `engine/src/hy4flash/run/hy4_main.hip.cpp`。
- バッチの生成処理は GPU Runner の初期化後に行われる。モデルファイル `--model` は必要で、モデルロード失敗時はバッチ処理に到達しない。
- `--dump-dfly-batch` が必須の有効化条件。`--dump-dfly-out` は出力先、`--out` はその代替、`--ctx` はコンテキスト上限、`--dump-dfly-temp` は greedy / sampling の選択、`--seed` は RNG seed に関係する。
- 負数または 0 を指定して有効な生成余地がなくなると、対象プロンプトは `max_T <= T0` でスキップされ、系列ファイルは出力されない。ソースにはこの値を拒否する validation がない。

## 出力とエラー

- マニフェストを開けない場合は `dump-dfly-batch: cannot open <path>` を stderr に出し、終了コード `1`。
- prefill または decode が失敗した場合は系列番号などを含むエラーを stderr に出し、`1` を返す。
- 系列ファイルを開けない場合は `dump-dfly: cannot write <path>` を stderr に出し、`1` を返す。
- ファイルを開いた後の `fwrite` と `fclose` の戻り値は検査されていないため、書き込み途中の失敗をこの処理が必ず検出するとはソースから確認できない。
- バッチ開始時に読み込み件数・生成上限・温度・出力先、系列ごとに出力先・生成長など、完了時に総数を stderr に表示する。
- 値が欠けると共通の引数処理が stdout に `ERR --dump-dfly-gen needs a value` を出して終了コード `2`。不明な引数は stderr に `unknown arg ...` を出して `2`。

## 根拠

- `engine/src/hy4flash/run/hy4_main.hip.cpp:368-370` — 値の格納先、既定値 384、および関連する温度の既定値。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:375-383,421-424` — 引数値の取得、欠落時の stdout と終了コード、`atoi` による変換。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:183-207` — マニフェストの読み込み・行の採否・出力先ディレクトリ作成。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:217-225,249-281` — 生成上限、温度に基づく選択、EOS による終了。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:302-331` — 系列ファイル名、バイナリ出力、成功時のログ。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:498-505` — 不明な引数のエラーと終了コード。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:613-615,632-639,687-708` — モデル必須条件、トークン有無の条件、`--tokens` と `--ctx` を含むコンテキスト自動値、バッチ実行への引き渡し。
