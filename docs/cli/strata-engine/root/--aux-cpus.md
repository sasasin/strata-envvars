# `strata` の `--aux-cpus`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata generate`（`generate.cpp` の parser。索引上の scope は root） |
| オプション | `--aux-cpus` |
| 別名 | なし |
| 値 | `off`、`auto`、または論理 CPU 番号のリスト（例: `24,26`、`24-27`） |

## 役割

CPU pool の worker と host thread を除くエンジンプロセスの thread を、指定された補助 CPU 集合へ配置する。対象には adaptive tier の job thread、prefill helper、CUDA driver の thread などが含まれる。thread の配置だけを変え、推論結果は変えない（`engine/src/program/generate.cpp:1463-1469`、`engine/include/strata/platform/aux_cpus.hpp:1-19`）。

## 使い方

```sh
strata generate --pack DIR --tokens "1,2,3" --aux-cpus auto
strata generate --pack DIR --tokens "1,2,3" --aux-cpus 24,26
```

値を省略すると parser は終了コード 2 で終了する（`engine/src/program/generate.cpp:3844-3847`）。

## 値と既定値

- 既定値は `off`。この場合、起動時には補助 CPU への配置を有効にしない（`engine/include/strata/platform/aux_cpus.hpp:130-148`）。
- `auto` は、host の物理 core の SMT sibling を先に使い、その後 worker がいない物理 core の CPU を使う。worker と同じ物理 core の CPU は選ばない。利用可能な CPU が残らない場合、配置計画は空になる（同 `:84-115`、`:375-405`）。
- リストは `24,26,30-31` のような非負整数のカンマ区切りと閉区間で指定する。各番号は 0..100000、範囲の終端は始点以上である必要がある。空要素、負数、文字、逆順の範囲などは拒否される。重複番号はソート後に除去される（同 `:50-81`）。
- `off` は起動時の配置を無効にする。`auto` またはリストを指定すると有効化を要求する（同 `:137-148`）。
- 同じオプションを複数回指定した場合、引数ループ内で同じ文字列変数へ代入するため、最後の指定値が使われる（`engine/src/program/generate.cpp:3842-3847`、`:3956-3964`）。

## 実行時の動作

parser は値を `Options::aux_cpus` に格納し、`parse_spec` で検証する。不正値は `strata generate: --aux-cpus takes off, auto or a CPU list ...` を stderr に出し、終了コード 2 で終了する（`engine/src/program/generate.cpp:3956-3964`、`engine/include/strata/platform/aux_cpus.hpp:137-148`）。

起動時は明示値が空でなければそれを採用し、空の場合は `STRATA_AUX_CPUS` を読み、どちらも空なら `off` として設定する。したがって `--aux-cpus off` は環境変数より優先し、明示的な空文字列は環境変数への fallback を起こす（`engine/src/program/generate.cpp:4715-4724`）。環境変数から得た不正値も設定時に拒否され、エラーを stderr に出して終了コード 2 となる。同じ環境変数は初期起動値として利用される（同 `:4717-4724`）。

Linux では、プログラムが利用可能な CPU 集合を thread pinning 前に記録し、pool の worker と host の CPU が分かった後に配置計画を作る。明示リストは、プロセスが利用できない CPU、host CPU、worker CPU を除外する。`auto` は topology 情報を使って計画する（`engine/include/strata/platform/aux_cpus.hpp:218-233`、`:118-127`、`:358-396`）。起動時に有効なら、既存の非 pool・非 host thread を走査して配置し、後から作られる Strata thread も有効中に自身を配置する（同 `:243-263`、`engine/src/program/generate.cpp:9037-9041`）。

serve mode では各 request の `strata_tune` に `aux_cpus=0|1` を指定でき、request ごとの値が起動時設定に優先する。値がない場合は起動時の有効状態に戻る。有効化時は各 request で既存 thread を再走査する（`engine/src/program/generate.cpp:18865`、`:18922-18927`、`:21431-21440`）。これは CLI 引数ではなく serve request の tuning key である。

## 適用条件と副作用

- `qwen35moe` family は通常 parser の option loop より前に `engine/src/qwen35` へ振り分けられる。この文書は `generate.cpp` parser の挙動を記録しており、別 parser で同オプションがどう扱われるかは確認できていない（`engine/src/program/generate.cpp:3804-3818`）。
- CPU affinity の変更実装は Linux 限定。Linux 以外では値の構文検証は行うが、設定・配置関数は no-op で、起動ログは `strata aux cpus: not available on this system` を返す（`engine/include/strata/platform/aux_cpus.hpp:407-422`）。
- 目標 CPU 集合が空なら有効化は行われず、起動ログに `none spare ...` と表示される。serve request から有効化を求めても計画がない場合は no-op（同 `:276-287`、`:392-405`）。
- 明示リストに含まれていてもプロセスが使えない CPU、host CPU、worker CPU は計画から黙って除かれる（同 `:118-127`）。
- Linux の thread affinity 取得・設定が失敗した thread は移動されず、該当 syscall の失敗自体を CLI エラーにはしない（同 `:179-191`）。移動した thread の元の affinity は保存され、無効化時に復元される（同 `:265-287`）。
- 位置変更に伴う副作用は thread の CPU affinity の変更であり、ファイルや推論結果を書き換える処理は確認できない（`engine/include/strata/platform/aux_cpus.hpp:18-19`）。

## 出力とエラー

- オプション値の欠落は `--aux-cpus needs a value` を stderr に出し、終了コード 2（`engine/src/program/generate.cpp:3844-3847`）。
- 値の形式が不正な場合は説明付きエラーを stderr に出し、終了コード 2（同 `:3956-3964`、`engine/include/strata/platform/aux_cpus.hpp:137-148`）。
- 起動時の計画は stderr に `strata aux cpus: ...` として出力される。計画がない場合や非 Linux の場合もその状態を示す（同 `:395-405`、`engine/src/program/generate.cpp:9037-9041`）。
- serve request で有効・無効が切り替わった場合は stderr に状態を出力する（`engine/src/program/generate.cpp:21431-21440`）。

## 根拠

- CLI 索引上の配置は `strata-engine` の root scope（`docs/cli/README.md:1036-1047`）。エンジン入口と parser の所在は `docs/cli/000_cli_tools.md:10`。
- parser、値の検査、環境変数 fallback: `engine/src/program/generate.cpp:3956-3964`、`:4715-4724`。
- 値の構文、CPU 集合の算出、thread affinity の処理: `engine/include/strata/platform/aux_cpus.hpp:50-81`、`:118-148`、`:179-191`、`:218-263`、`:375-422`。
- serve request 単位の tuning: `engine/src/program/generate.cpp:18865`、`:18922-18927`、`:21431-21440`。

調査時点で `STRATA_AUX_CPUS` の個別環境変数文書は見つからなかったため、環境変数の全仕様は本書では扱っていない。
