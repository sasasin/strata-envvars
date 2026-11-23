# `--dump-dfly-batch`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4`（CUDA/HIP 版、root） |
| オプション | `--dump-dfly-batch` |
| 別名 | なし |
| 値 | manifest ファイルのパス（文字列） |

## 役割

manifest に列挙した token ID 列を順に GPU で推論し、各列の token、隠れ状態、Hy4 の指定層の KV、次 token 候補などを `seq_*.bin` に保存するバッチ出力経路を選びます。通常の単一 prompt 生成ではなく DFly 用データの dump を行います。モデルファイル `--model`（別名 `--native`）は引き続き必須で、モデル読込と Runner 初期化の後にこの経路へ入ります。

## 使い方

```sh
strata-hy4 --model model.strata --dump-dfly-batch prompts.txt --dump-dfly-out ./dfly-output
```

`prompts.txt` は1行につき token ID 列を記述し、空行および `#` で始まる行は読み飛ばします。生成長は `--dump-dfly-gen`、sampling 温度は `--dump-dfly-temp`、出力先は `--dump-dfly-out` で調整できます。manifest がなくても `--tokens` はこのバッチ経路の入力には使われません。

## 値と既定値

- オプションは値を1つ受け取り、parser はその文字列を manifest パスとして保存します。数値形式やファイル存在を parser 段階では検証しません。省略時に値がなければ共通の `nxt()` が `ERR --dump-dfly-batch needs a value` を stdout に出して終了コード 2 で終了します。
- 同じオプションを複数回指定した場合は、引数走査で後に現れたパスが残ります。空文字列を値にすると、後段の `!dump_dfly_batch.empty()` 判定を通らず、バッチ経路は選ばれません。
- ファイルを開けない場合は stderr に `dump-dfly-batch: cannot open <path>` を出し、戻り値 1 になります。
- manifest は行ごとに整数を読み、8個以上読めた行だけを prompt として採用します。行頭が `#` の行と空行は無視します。トークン ID の範囲検証はこの処理にはなく、整数として読めない箇所に達すると、その行の残りは読み取りを止めます。

## 実行時の動作

parser はこの値を `dump_dfly_batch` に格納します。`--model` がない場合は通常どおり usage を stderr に出して終了コード 2 となり、モデルをロードした後に `Runner` を初期化します。その後、値が空でなければ `run_dump_dfly_batch` を呼び、そこで返る結果をプロセスの終了値として返します。従って GPU 初期化・モデルロード失敗はバッチ処理に入る前に発生し得ます。

manifest を読み、各採用行を prompt として処理します。prompt が Runner の context 上限を超える場合は先頭から `r.Tc` token に切り詰めます。生成上限は `min(r.max_ctx - 8, prompt長 + --dump-dfly-gen)` で、これが prompt 長以下ならその prompt は出力されず次へ進みます。各 token の logits から top 64 を求めて greedy または sampling で次 token を追加し、EOS token または ID `120008` で停止します。

バッチ分岐での設定の関係は次のとおりです。

- `--dump-dfly-out` が空でなければ出力先に使い、空なら `--out` の値（既定値 `.`）を使います。出力ディレクトリは作成されます。
- `--dump-dfly-gen` の既定値は `384` です。`--ctx` が未指定または 0 以下の場合、この経路では最大 context を `dump-dfly-gen + 512` にします。`--ctx` が正ならその値を使います。
- `--dump-dfly-temp` の既定値は `-0.6` です。負値は絶対値を sampling 温度として使い、prompt の番号が 3 で割って 2 余る場合だけ sampling、それ以外は greedy になります。0 以下のうち 0 は常に greedy、正値は全 sequence で sampling です。sampling は top 64 候補内で累積確率 0.95 までを使います。
- `--seed` の値が RNG seed に渡されます。seed が 0（既定値を含む）の場合は内部 seed `20261120` が使われます。
- `--tokens` や通常生成用 `--gen` の値はバッチ処理の manifest・生成長には使われません。manifest の列が空でも、通常の `no tokens` 検査はバッチ経路では適用されません。

各採用 prompt の出力名は `seq_%04zu.bin`（prompt の0始まりの行番号ではなく採用後の順番）です。同名ファイルがあれば `wb` で切り詰めて上書きします。ファイルには順に8個の int32 header（magic `0x44464C59`、version `1`、token 数、prompt token 数、64、5、HID、MLA_ROW）、token ID、各 token の hidden state、5層分の KV、top-64 token ID、top-64 log probability、tail probability が書かれます。書き込み先ファイルを作れない場合は stderr に `cannot write` を出し、戻り値 1 です。

## 適用条件と副作用

- 対象は `strata-hy4` CUDA/HIP 実装です。README 索引上の同じツール ID の Metal・SYCL コマンド階層にはこのオプションは列挙されていません。
- manifest を読み、GPU 推論と GPU/CPU 間コピーを行い、出力ディレクトリを作成してバイナリファイルを書きます。既存の同名 `seq_*.bin` は上書きされます。
- prompt 行の token ID を有効範囲と照合する処理、出力ディレクトリを既存データごと消去する処理、`fwrite` の戻り値を検査する処理は確認できません。異常な token ID や途中の書込失敗時の結果は、この実装からは確定できません。
- GPU API 呼出しは `HCK` マクロを通じたエラー処理に委ねられます。その詳細な表示・終了動作はこのオプションの処理本体だけからは判断しません。

## 出力とエラー

- 処理開始時・各 sequence 完了時・全体完了時の進捗は stderr に出力されます。ログには出力ファイル名、prompt/生成 token 数、温度、経過時間が含まれます。
- manifest を開けない、prefill/decode に失敗する、または出力ファイルを作れない場合は stderr にエラーを出し、戻り値 1 で終了します。
- option 値が不足した場合とモデルが指定されていない場合は終了コード 2 です。数値の妥当性について `--dump-dfly-gen` / `--dump-dfly-temp` 自体の明示的 validation は見当たりません。

## 根拠

- `engine/src/hy4flash/run/hy4_main.hip.cpp:368-370` — dump 関連変数と既定値。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:375-384,421-424` — 引数値の取得と parser 登録。専用の数値 validation はなく、共通の値不足経路は `375-384`。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:498-505,613-615` — 未知引数と model 必須条件。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:632-639,687-708` — 通常 token の読み込み、空 token 判定の例外、context 既定値、Runner 初期化後のバッチ分岐および関連オプション引渡し。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:183-207` — manifest の読込・行の採用条件と開始ログ。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:217-301` — prompt 切り詰め、生成上限、温度による選択、EOS 停止、prefill/decode エラー。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:302-330` — 出力ファイル名、上書きモード、データの書込順、書込不能エラーと完了ログ。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:99-181` — top-64 logits と tail probability の抽出処理。
- `engine/src/hy4flash/run/hy4_dfly2.hip.h:25-35` — `SampleOpts.seed` の既定値が 0 であること。
- `engine/src/hy4flash/run/hy4_kernels.hip.h:10`、`engine/src/hy4flash/run/mla_attn.hip.h:27`、`engine/src/hy4flash/run/hy4_dfly2.hip.h:189` — HID、MLA_ROW、dump が参照する5層定数。
- `docs/cli/README.md:1277-1299` — `strata-hy4` CUDA/HIP scope と指定オプションの索引リンク。
- `docs/cli/000_cli_tools.md:11` — `strata-hy4` のツール ID、実装入口、`root/`・`metal/`・`sycl/` の階層。

調査は記載 commit のソースに限定しました。安全な同一 revision の既存 CLI help は確認していません。出力バイナリの reader/schema 利用側、無効 token ID の後続挙動、および `HCK` の詳細なエラー処理はこの文書の調査範囲では確定していません。
