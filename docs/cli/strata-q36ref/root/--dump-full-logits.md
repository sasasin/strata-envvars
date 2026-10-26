# --dump-full-logits

調査対象: Strata commit 4b9e05a2a806a3fe24f7b2560d98626c37dade35（2026-10-26 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | strata-q36ref |
| コマンド | strata-q36ref（Qwen3.6 reference CLI、トップレベル） |
| オプション | --dump-full-logits |
| 別名 | なし |
| 値 | 必須の出力ファイル名。内容は各生成 step の全 vocabulary logits を float で記録したバイナリ |

## 役割

各生成 step で得た全 token の logits をファイルへ記録します。ソースコメントでは、--force による teacher-forcing 列と組み合わせ、tools/qwen35/kl.py で KL を確認する用途として説明されています（src/qwen35/q36ref.cu:25-31）。この CLI は CMake の strata-q36ref target として定義される reference executable です（CMakeLists.txt:771-775）。索引では照合・開発用 CLI とされ、現行 Release への同梱は確認できていません（[docs/cli/README.md](../../README.md)）。

## 使い方

~~~sh
strata-q36ref --model Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf \
  --tokens 248045,846,198 --n 4 --dump-full-logits /tmp/q36-logits.bin
~~~

実行時には GPU 上でモデルを処理する reference executable が必要です。--tokens または --tokens-file に prompt token IDs を渡します。--force を併用する場合の例:

~~~sh
strata-q36ref --model Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf \
  --tokens 248045,846,198 --force 320,13 --dump-full-logits /tmp/q36-forced-logits.bin
~~~

usage/parser は src/qwen35/q36ref.cu:25-31, 722-764 にあります。独立した --help 分岐はなく、未知の引数は usage を stderr に出して終了コード 2 になります（同 :759-764）。

## 値と既定値

- 値は次の argv 要素から一つ取得します。値を省略すると q36ref: --dump-full-logits needs a value を stderr に出して終了コード 2 で終了します（src/qwen35/q36ref.cu:727-733, 753）。
- パスの書式、拡張子、書き込み可能性の事前検証はありません。オプション未指定時はファイルを開かず、全 logits の記録もしません（同 :723-724, 792）。空文字の argv 値では dump_full.empty() が真となり、ファイル出力が無効になります（同 :792）。
- 同じオプションを複数回指定した場合、parser ループで文字列が上書きされ、最後の値だけが後で開かれます（同 :725-765, 792）。

## 実行時の動作

- 指定パスを fopen(..., "wb") で開きます。既存ファイルなら切り詰め、新規なら作成します。開くタイミングはモデル読み込みと GPU state 初期化の後です（src/qwen35/q36ref.cu:775-793）。
- prompt の最終位置から生成を始め、各生成 step で GPU 上の logits 全体を host 側の std::vector<float> にコピーし、その配列を fwrite します。1 record は vocabulary size V 個の float、書き込み順は step ごとの [step][vocab] です（同 :789-793, 802-816）。ソースコメントもデータを f32, [step][vocab] と記しています（同 :30-31）。
- 既定の --n は 64 です。--force が空でなければ、forced token 数 + 1 が n_gen に設定され、--n の値より優先します。ログ出力には greedy token IDs が引き続き使われますが、次の forward 入力 token は forced 列から順に選ばれます（同 :723-724, 766-770, 802-815, 826-831）。したがって、記録 step 数は --force なしなら --n、空でない --force ありなら forced token 数 + 1 です。各 step の logits は、その step の入力 token を処理した結果です。
- --ctx は既定 4096 で、全処理位置数は prompt token 数 + n_gen - 1 として検査されます。--dump-full-logits はこの計算や logits の選択を変えません（同 :723-724, 797-800）。
- --dump-logits は別ファイルに各 step の top-2 ID/logit を記録する独立出力です。両方を指定すると、全 vocabulary と top-2 の両方が出力されます（同 :790-792, 806-819）。

## 適用条件と副作用

- ファイルはモデル読み込み後に "wb" で開かれます。既存の指定先を破壊的に切り詰めるため、例では /tmp の新しいファイル名を使っています（src/qwen35/q36ref.cu:775-793）。
- fopen の戻り値が null でもエラーを表示せず、ff が null のままなら記録を飛ばして処理を続けます。fwrite の戻り値も検査しません。そのため、出力ファイルを作成できない場合や途中の書き込みに失敗した場合に、コマンドが成功扱いとなり得ます（同 :792, 815, 825-831）。
- --ctx 超過はファイルを開いた後に判定されます。超過時は stderr に位置数のエラーを出して終了コード 2 で戻りますが、この経路では開いた fl / fg / ff を閉じていません。--dump-full-logits の指定先はすでに作成または切り詰められている可能性があり、logits の書き込みには到達しません（同 :790-800）。
- モデル読み込みに失敗した場合は出力ファイルを開く前に終了し、stderr にエラーを出して終了コード 1 になります（同 :775-785）。
- ファイルの記録量は概ね step 数 × vocabulary size × sizeof(float) です。ソースでは float 配列をそのまま binary write しており、ヘッダー、byte order、float 表現の正規化は付加していません（同 :793, 815）。異なる環境間でのバイナリ互換性はソースから保証できません。

## 出力とエラー

正常経路では、logits ファイルに加えて stdout に gen: <token IDs...>、stderr に処理位置数と時間の計測行が出ます（src/qwen35/q36ref.cu:826-831）。--dump-full-logits 固有の open/write 失敗メッセージや終了コード設定はありません。前述の通り、その失敗は検出されず成功終了する場合があります（同 :792, 815, 825-831）。

## 根拠

- parser、値取得、unknown option の usage: src/qwen35/q36ref.cu:722-764
- forced 列による n_gen 上書き、必須引数、モデル読み込み: src/qwen35/q36ref.cu:766-785
- fopen("wb")、context 上限、各 step の logits host copy / binary write、close と終了表示: src/qwen35/q36ref.cu:786-831
- reference CLI の用途と dump 形式: src/qwen35/q36ref.cu:25-31
- CMake executable target: CMakeLists.txt:771-775
