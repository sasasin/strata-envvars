# `--bench-tg`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | Qwen3.6 専用 engine parser（`strata --model <Qwen3.6 GGUF>` または `strata-q36`） |
| オプション | `--bench-tg` |
| 別名 | なし |
| 値 | 整数として `std::atoi` で変換。正の値が token generation 計測数として使われる |

## 役割

Qwen3.6 engine の生成段階（TG）を、合成 token prompt の後で逐次 greedy decode し、token/s を表示します。実際のユーザー prompt や文章生成品質を評価するものではありません。Qwen3.6 専用 parser のオプションであり、通常 engine parser の同名フラグを意味しません。

## 使い方

```sh
strata-q36 --model /models/qwen3.6.gguf --bench-tg 128
```

または、Qwen3.6 の GGUF architecture が `qwen35moe` の場合は次のように `strata` から起動できます。

```sh
strata --model /models/qwen3.6.gguf --bench-tg 128
```

`--bench-pp` は省略できます。その場合も benchmark は長さ 1 token の prompt を使います。両方を指定すると、`--bench-pp` が prompt 長、`--bench-tg` が decode token 数になります。

## 値と既定値

- 値は必須です。省略して次の引数がない場合、`strata-q36: --bench-tg needs a value` を標準エラーへ出し、終了コード 2 で終了します。
- 既定値は 0 です。変換は `std::atoi` で行われ、`--bench-tg` 自体に範囲検証や形式エラー処理はありません。`atoi` が 0 を返す文字列や 0 以下の値では、このフラグ単独では benchmark 分岐に入りません。
- `--bench-tg` が正なら `--bench-pp` の値にかかわらず benchmark 分岐に入り、prompt token 数は `max(bench_pp, 1)` です。`--bench-pp` が省略時 0 または 0 以下なら prompt は 1 token です。
- alias はありません。

## 実行時の動作

Parser は `--bench-tg` の次の argv を `atoi` で `bench_tg` に格納します。モデル読込と `Engine` 初期化、expert 配置、state reset、必要なら warmup を行った後、`bench_pp > 0 || bench_tg > 0` のとき benchmark に入ります。各回、固定 seed `1234` の乱数 generator から `[0, 200000)` の整数 token ID 列を作り、状態を reset して prompt を処理します。その後 `E.greedy()` で次 token を取り、`--bench-tg N` の回数だけ 1 token を処理して再度 greedy token を取得します。これを 3 回実行します。

標準出力には各回 `bench <回数>: pp<token数> <tok/s>, tg<指定数> <tok/s>` の形式で表示されます。TG の計測時間は最初の greedy 呼び出しと各 token の処理・greedy 呼び出しを含み、TG tok/s は指定 token 数をその時間で割ります。`--bench-tg 0` で `--bench-pp` のみ正の場合は benchmark 自体は実行され、TG は `tg0 0.0 tok/s` と表示されます。

## 適用条件と副作用

- `strata` は `--model` または `--native` が指す GGUF の architecture を読み、`qwen35moe` なら Qwen3.6 engine parser へ処理を渡します。それ以外のモデルに対する `strata` の挙動はこの parser の対象外です。
- 独立 executable `strata-q36` は CMake で `STRATA_HIP_GFX906` でない場合に定義されています。リポジトリのソース確認だけでは、特定の配布物に含まれるかは断定できません。
- 起動時にモデルを GPU へロードし、engine buffer と routed experts を配置します。benchmark の前に通常 warmup も行います。`--no-warmup` を併用すると warmup を省略しますが、モデル読込・engine 初期化・expert 配置は省略されません。
- `--serve` を同時指定すると、engine 初期化後に serve を開始して benchmark 分岐へ進まないため、`--bench-tg` は実行されません。
- benchmark が作る token ID 列は実 prompt ではなく、parser/benchmark 側にモデルの `n_vocab` と照合する明示的な範囲検査はありません。token embedding kernel 側の範囲外入力時の挙動は本調査では確認していません。
- 各反復で `E.reset()` により推論状態を初期化します。モデルファイルを書き換える処理は benchmark 分岐にありません。

## 出力とエラー

- 各計測行は stdout に出力され、行ごとに flush されます。
- モデル指定がなければ標準エラーに `--model is required` を出して終了コード 2、モデルの load 失敗または load 中の例外は標準エラーに内容を出して終了コード 1 です。
- CUDA runtime 呼出しが失敗すると、失敗した式・CUDA エラー・ソース位置を標準エラーに出して `exit(1)` します。benchmark 固有の token 数検証や性能しきい値による失敗分岐はありません。
- 未知の引数は usage を標準エラーに出して終了コード 2 です。usage の例示では `--bench-pp N --bench-tg N` が併記されていますが、実際の benchmark 条件は両方の正値を要求せず、どちらか一方が正なら分岐します。

## 根拠

- `src/qwen35/q36_engine.cu:3735-3765` — Qwen3.6 parser と `--bench-tg` の値変換。`3744-3746` は値不足時の終了処理。
- `src/qwen35/q36_engine.cu:3790-3815` — 未知引数、モデル必須、モデル load のエラー経路。
- `src/qwen35/q36_engine.cu:3888-3917` — warmup 後の serve 優先、benchmark 条件、乱数 prompt、3 回の計測、表示、通常 prompt 必須条件。
- `src/qwen35/q36_engine.cu:67-74` — CUDA 呼出し失敗時の標準エラー出力と終了処理。
- `src/qwen35/q36_engine.cu:2433-2459, 2780-2784` — benchmark が呼ぶ token processing と同期 greedy 結果取得。
- `src/program/generate.cpp:2393-2408` — `strata` が GGUF architecture により Qwen3.6 engine へ切り替える条件。
- `CMakeLists.txt:776-795` — `strata-q36` target と gfx906 除外条件。
- `docs/cli/README.md:1318-1328` — `qwen36` parser scope とこのオプションの索引リンク。

## 調査範囲

同一 revision のソース、CMake 定義、CLI 索引を確認しました。ビルド済み CLI の `--help`、Release artifact、各 GPU/backend での実行結果は確認していません。ビルド、GPU 実行、性能測定、テストは行っていません。
