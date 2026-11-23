# `strata-engine` Qwen3.6 `--dump-expert-profile`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata` の Qwen3.6 専用 parser（または `strata-q36`） |
| オプション | `--dump-expert-profile` |
| 別名 | なし |
| 値 | 出力ファイルのパス（文字列） |

## 役割

Qwen3.6 エンジンが hybrid expert 配置で動作するとき、各 routed expert への routing score を順位にして STRP v1 形式で保存します。生成したファイルは次回実行の `--expert-profile` に渡せます。これは引数を受け取っただけで即時保存する機能ではなく、warmup 後の処理で `rebalance()` が呼ばれた時点の score を出力する機能です（`engine/src/qwen35/q36_engine.cu:3413-3443,3445-3450`）。

## 使い方

```sh
# Hybrid 配置になる環境でプロンプトを処理し、routing profile を保存する
strata --model ./qwen36.gguf --tokens '1 2 3' --dump-expert-profile ./qwen36-routing.strp

# 保存済み profile を次の実行で expert 配置の順位入力として使う
strata --model ./qwen36.gguf --tokens '1 2 3' --expert-profile ./qwen36-routing.strp
```

`strata-q36` の専用実行ファイルでも同じ parser が使われます。モデル指定は `--model` または `--native` です（`engine/src/qwen35/q36_engine.cu:5354-5355,5387,5391`）。上の例では出力ファイルを新しい名前にして、既存ファイルを意図せず置き換えないようにしてください。

## 値と既定値

値は必須のパス文字列です。parser は次の argv 要素をそのまま `dump_profile` に代入し、拡張子・空文字列・パスの存在や書き込み可能性は検証しません。値を省略すると `strata-q36: --dump-expert-profile needs a value` を stderr に出して終了コード 2 で終了します（`engine/src/qwen35/q36_engine.cu:5349-5352,5387`）。同じオプションを複数指定した場合は parser が都度代入するため、最後の値が残ります（同 `:5348-5352,5387`）。

## 実行時の動作

- オプションの値は `Engine::dump_profile` に渡されます（`engine/src/qwen35/q36_engine.cu:1573-1579,5466-5469`）。
- `dump_expert_profile()` は `dump_profile` が空、またはモデル未設定なら何もせず戻ります。通常の呼び出し元 `rebalance()` は、モデルの `m->hybrid` が偽、環境変数 `STRATA_Q36_FIXED_SLOTS` が設定済み、または warmup 中なら profile 保存を含めて何もしません（同 `:3413-3415,3445-3450`）。`m->hybrid` は expert 配置が VRAM 内で完結せず CPU expert pool を使う配置で設定されます（同 `:4318-4348`）。
- 通常の prompt 処理では prompt 完了時（または chunk callback が継続を止めた時）に hybrid 配置なら `rebalance()` が呼ばれます。decode では保持した行の位置が32の倍数になった境界で呼ばれ、batch decode では32 window ごとです（同 `:1866-1885,3743-3749,3807-3814`）。warmup は `warming` を立てて処理し、終了後に score をゼロにするため、warmup 自体の profile は出力されません（同 `:4026-4046`）。
- 出力対象は main model の各 layer と expert の全組です。`hy[li].score[x]` の降順、同点なら layer/expert index 順に並べます。score がない組は 0 として扱います。ファイルは `STRP` の4 byte magic、5個の `uint32_t` (`version=1`, layer数, expert数, 全 layer の slot 数合計, pair 数)、続けて各組の `uint16_t layer` と `uint16_t expert` の列です（同 `:3417-3428,3432-3439`）。
- 保存は `<指定パス>.partial` を `wb` で開いて書き、その後 `rename()` で指定パスへ移します。すでに存在する `.partial` は `fopen(...,"wb")` で切り詰められます。最終パスの既存ファイルを保護する処理はなく、rename の置換可否は実行 OS の `rename()` に従います（同 `:3429-3442`）。
- 保存は score の半減処理より前です。したがって出力はその rebalance 境界で数えた routing score のランキングで、slot の入れ替えに先立つ snapshot です（同 `:3445-3450,3458-3495`）。次の実行で `--expert-profile` を使うと、この STRP v1 の順位を peer tier 配置などに使う経路があります（同 `:4072-4077,4091-4109`）。

## 適用条件と副作用

- 対象は `strata-engine` の Qwen3.6 専用 parser のみです。索引上の scope は `strata-engine/qwen36` で、汎用 engine parser の `root/` とは別です（`docs/cli/README.md:1240-1250`; parser: `engine/src/qwen35/q36_engine.cu:5387`）。
- VRAM に全 expert を配置できる場合は `m.hybrid` が立たず、`rebalance()` が何もしないので、このオプションを指定しても出力されません（`engine/src/qwen35/q36_engine.cu:4318-4335,4343-4348,3445-3450`）。
- ファイルへの書き込みと rename はエンジンの処理中に行われます。各 rebalance 境界で同じパスへ再度書き込み、最終ファイルを更新しようとします（同 `:3429-3442,3450`）。頻度や出力可否は実行モードだけでは決まらず、hybrid 配置と rebalance の到達条件にも依存します。
- `--expert-profile` は入力 profile であり、本オプションは出力先です。併用時のパス衝突を防ぐ検査は確認できません。異なるパスを指定してください（同 `:5387,5391,5466-5473`）。

## 出力とエラー

`.partial` を開けない場合は `strata-q36: cannot write <partial-path>` を stderr に出してその保存処理を中断します。最終パスへの `rename()` に失敗した場合は `strata-q36: cannot rename <partial-path>` を stderr に出します。どちらも helper はエラーを返さず、これらの失敗を理由に CLI の終了コードを変更する処理はこの helper 内にありません（`engine/src/qwen35/q36_engine.cu:3429-3443`）。

`fwrite()` と `fclose()` の戻り値は検査されていないため、書き込み途中の I/O エラーを診断・伝播する動作は確認できません（同 `:3434-3442`）。また `.partial` の残骸を削除する処理もこの helper にはありません。

## 根拠

- `engine/src/qwen35/q36_engine.cu:5349-5352,5387` — 値を必要とする parser とオプションの受理。
- `engine/src/qwen35/q36_engine.cu:1573-1579,5466-5469` — 値の保持と `Engine` への設定。
- `engine/src/qwen35/q36_engine.cu:3413-3443` — score の順位付け、STRP v1 の出力、`.partial` と rename、エラー表示。
- `engine/src/qwen35/q36_engine.cu:1866-1885,3445-3450,3743-3749,3807-3814,4026-4046` — score の計数、出力の呼び出し境界、warmup 抑止。
- `engine/src/qwen35/q36_engine.cu:4247-4348` — VRAM 内配置と hybrid 配置の分岐。
- `engine/src/qwen35/q36_engine.cu:4072-4109` — STRP profile を入力として読む関連経路。
- `docs/cli/README.md:1240-1250` — `strata-engine/qwen36` scope と索引リンク。
