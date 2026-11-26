# `strata`（エンジン引数）`--max-new`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（エンジン引数、トップレベル） |
| オプション | `--max-new` |
| 別名 | なし |
| 値 | 生成するトークン数。10進整数として `int64_t` に変換され、正の値が必要 |

## 役割

通常の生成実行で、プロンプトの続きとして生成するトークン数の上限を指定します。既定値は16です。EOS による停止や `--spec-follow` の入力長によって、実際の出力はこの上限より短くなることがあります。

## 使い方

```sh
# モデルと PLE の GGUF、および実在するトークン ID に置き換えて実行
strata --native model-00001-of-00002.gguf --ple-gguf model-00002-of-00002.gguf \
  --tokens 1,2,3 --max-new 64
```

## 値と既定値

- 省略時は `Options::max_new` の初期値16です（`engine/src/program/generate.cpp:756-760`）。help の表示も既定値16としています（同 `:1267`）。
- parser は次の引数を `std::atoll` で変換します。値を省略すると `--max-new needs a value` を stderr に出して終了コード2、変換後が0以下なら後段の検証で拒否されます（同 `:3842-3846`, `:3870`, `:5222-5225`）。変換時に数字として読めない接尾辞を厳密に拒否する処理はありません。
- 同じオプションを複数回指定したときは、parser が順に代入するため最後の値が残ります（同 `:3842-3847`, `:3870`）。

## 実行時の動作

通常の生成では、プロンプト末尾の位置から予測したトークンを出力列に加え、列の長さが `--max-new` に達すると生成ループを終了します。したがってこれはプロンプト長を含む総トークン数ではなく、新規出力数の上限です（`engine/src/program/generate.cpp:24440-24447`）。`--spec` による投機的生成でも上限が参照され、`--spec-follow` を使う場合は指定上限と continuation ファイルのトークン数の小さい方が上限になります（同 `:24459-24466`, `:24473-24483`）。

`--max-context` と合わせて、プロンプトと生成枠の両方が収まる必要があります。エンジンは `max_new <= max_context` および `prompt token count <= max_context - max_new` を検査します（同 `:5217-5225`）。`--logits-stride` を1より大きくする場合は、`--max-new 1` と `--dump-logits` の両方が必須です（同 `:5201-5203`）。

`--dump-logits` を併用すると、予定するログ出力行数の計算にこの値が使われます。出力ファイルは `wb` で開かれるため、同名ファイルがあれば上書きされます（同 `:10652-10676`）。

## 適用条件と副作用

- 通常の生成では正の値が必須で、プロンプト長との合計が `--max-context` に収まらない値は拒否されます。拒否時は stderr に `positive --max-new and --max-context must fit the prompt and generation` を出し、終了コード2です（`engine/src/program/generate.cpp:5222-5225`）。後段にも容量検査があり、違反時は具体的な prompt / generation 数を stderr に出して終了コード2です（同 `:6152-6155`）。
- `--stop-eos` が有効な実行では、生成トークンが EOS ID に一致すると上限前でも停止します（同 `:24444-24447`）。
- `--serve` では、トークン入力を伴わない起動時に通常の prompt と生成数の組を作る代わりに、内部で1トークンの初期入力と `max_new=1` を設定します（同 `:4996-5000`）。その後の `GEN` / `GENI` リクエストはプロトコル内で個別の `max_new` を受け取り、その値を prompt と context に対して検証します（同 `:18818-18824`, `:18974-19017`）。このサーバー経路では起動時の `--max-new` を各リクエストの上限として扱うことは確認できません。
- Qwen3.6-35B-A3B のモデルは通常 parser より前にファミリー専用 `qwen35::run` へ振り分けられます（同 `:3804-3818`）。同モデルでの別 parser の仕様はこの文書の対象外です。

## 出力とエラー

値がない場合は stderr に不足を表示し、終了コード2で終了します（`engine/src/program/generate.cpp:3844-3846`）。0以下、または prompt / generation が context に収まらない場合も、上記の診断を stderr に出して終了コード2です（同 `:5222-5225`）。

## 根拠

- `engine/src/program/generate.cpp:756-760`, `:1267`: 既定値と help 表示。
- `engine/src/program/generate.cpp:3842-3847`, `:3870`: 引数取得、`atoll` 変換、重複時の代入。
- `engine/src/program/generate.cpp:5201-5203`, `:5217-5225`: `--logits-stride` との条件、および正数・context 検証。
- `engine/src/program/generate.cpp:24440-24447`, `:24459-24483`: 通常の生成停止、EOS 停止、投機生成と `--spec-follow` の上限。
- `engine/src/program/generate.cpp:4996-5000`, `:18818-18824`, `:18974-19017`: serve 起動時の内部値とリクエストごとの `max_new`。
- `engine/src/program/generate.cpp:10652-10676`: logits 出力行数とファイルオープン。
- SYCL parser / validation も同じ既定値・`atoll` 変換・制約を持ちます（`engine/sycl/src/program/generate.cpp:1909`, `:2615-2639`）。実行時の共通生成ループの挙動を含め、個々の backend での生成結果や性能差はこのソース確認だけでは評価していません。
