# `STRATA_KEEP_MAPPING`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`--mmap-experts` のファイル層が非バッファ読み取りになったとき、Strata がその元ファイルのマップを閉じる処理を抑止する、設定有無だけを見る A/B 用の変数です。変数が設定されていれば、値が `1` かどうかに関係なくマップを保持します。設定されていない場合、条件を満たす Windows 実行では起動時ロード前またはその後にマップ解除を試みます。対象のファイル層は `experts.bin`、または native pack の expert shard を読み込む GGUF です（`engine/src/program/generate.cpp:8621-8627,8654-8668,12259-12271`）。

マップの保持自体はファイル層の読み取り方式を切り替えません。非バッファ読み取りが選ばれている間も、別途開いた direct I/O の読み取りは継続します。Strata の実装コメントは、Windows でマップが残ると同一ファイルへの非バッファ読み取りが逐次化されるとしており、この変数はその差を比べる用途です（`engine/include/strata/core/expert_source.hpp:912-919,928-935`）。

## 値と判定

両方の読み取り箇所とも `std::getenv("STRATA_KEEP_MAPPING") == nullptr` を条件にしています。文字列を変換・比較せず、未設定なら解除処理を許可し、設定済みならその処理を飛ばします。したがって空文字も設定済みとして扱われ、`0`、`false`、大文字小文字、前後の空白、末尾の文字にも特別な意味はありません（`engine/src/program/generate.cpp:8663,12261`）。

| 条件 | unset | 設定されている例 | 判定される無効値の例 |
|---|---|---|---|
| Windows、ファイル層が非バッファ読み取り | マップ解除を試す | `1`、`0`、`false`、空文字のいずれも解除を抑止 | 値としての無効値はない。存在すれば抑止 |
| Linux、ファイル層が非バッファ読み取り | 後段の解除呼び出しへ進むが、本番用 `drop_mapping` は解除せず理由 `not Windows` を返す | 呼び出しとその結果ログを抑止 | 値としての無効値はない。存在すれば抑止 |
| その他の OS、またはファイル層がバッファ読み取り | この変数によるマップ解除条件に入らない | 同左 | 同左 |

## 有効になる条件

- 実行経路が `engine/src/program/generate.cpp` の `FileExpertSource` を使う generate/serve 経路であること。別実装の `engine/sycl/src/program/generate.cpp` にはこの名前の読み取りがありません（`engine/src/program/generate.cpp:8621-8628,8745-8746`; `engine/sycl/src/program/generate.cpp` 全体の名前検索では参照なし）。
- `o.mmap_experts` が有効で、`--mmap-experts`、resident mode、`--ssd-experts`、または arena 不足時の file fallback などからファイル層が選ばれていること。arena がそのまま使われる場合は `srcp == &arena_src` となり、後段の解除条件を満たしません（`engine/src/program/generate.cpp:8621-8628,8745-8747,8871-8911,8972`）。
- `src.unbuffered()` が真であること。最初の解除判定は `o.resident_budget > 0 || o.ssd_experts` のとき `set_unbuffered` が成功した場合だけです。予算なしで `STRATA_UNBUFFERED_LOAD` が設定されていても、この箇所では file cache のままです（`engine/src/program/generate.cpp:8654-8674`）。
- Windows では同じ unset 判定が非バッファ読み取りの確立直後と、startup load・resident 構築・必要な recheck の後の2箇所にあります。最初の解除に失敗した場合、後段でもマップが残っていて非バッファ読み取りなら再度解除を試します（`engine/src/program/generate.cpp:8654-8668,12108-12117,12259-12265`）。
- Linux では後段の条件だけがコンパイルされますが、本番用 `drop_mapping` は `not Windows` を返して解除しません。Linux 側の解除処理は `STRATA_TEST_UNMAP_GGUF` を使うテスト経路として実装されています（`engine/src/program/generate.cpp:12259-12265`; `engine/src/core/expert_source.cpp:2910-2961`）。
- 別の CLI 引数が `STRATA_KEEP_MAPPING` を上書きする処理はありません。`STRATA_UNBUFFERED_LOAD` は非バッファ読み取りの選択に関わりますが、マップ保持判定とは独立です（`engine/src/core/expert_source.cpp:959-972,2842-2858`; `engine/src/program/generate.cpp:8663,12261`）。

## 実行時の詳細

読み取り箇所は2つとも関数内 static cache ではなく、その場で `getenv` を呼びます。1つ目は `_WIN32` の条件付きコードで、`set_unbuffered` 後に `ub` が真なら `drop_mapping_verified` を呼びます。同関数は Windows でマップ上の最初の expert blob と direct read の内容を照合してから解除し、照合失敗時は mapped fallback を残します（`engine/src/program/generate.cpp:8654-8668`; `engine/src/core/expert_source.cpp:3001-3029`）。

2つ目は startup load と resident RAM の構築・file tier の再判定を終えた後に実行されます。条件は `srcp == &src`、非バッファ読み取り中、まだ未解除、かつ変数未設定です。Windows の `drop_mapping` は GGUF shard のマップ、または `experts.bin` のマップと対応 handle を閉じ、以降の expert 読み取りを direct handle 側へ回します。`--ple-io mmap` / `ram` が expert を含む GGUF shard を別途マップしている場合、その shard は残り読み取りの直列化が続く旨の note も出します（`engine/src/program/generate.cpp:12259-12271`; `engine/src/core/expert_source.cpp:2910-2943`）。

変数の値は `STRATA_UNBUFFERED_LOAD` や CLI から合成されず、Strata がこの名前を子プロセスへ転送する実装も見つかりません。Strata 内で実行中に値を書き換える箇所もありません。通常のプロセスでは起動時の環境値が各判定に使われます。

## ログと測定値

- unset で最初の Windows 判定に入ると、解除の成否に応じて `strata generate: the mapped view of the experts is closed before startup load (...)` または `... stays open before startup load (...)` を stderr に出します（`engine/src/program/generate.cpp:8663-8668`）。
- unset で後段判定に入り、マップが未解除なら `strata generate: the mapped view of the experts is closed (...)` または `... stays open (...)` を stderr に出します。解除後の GGUF で `--ple-io mmap` / `ram` が対象 shard を保持する場合は `strata generate: note: --ple-io ... keeps ... mapped; if that shard holds experts, their reads stay serialized (--ple-io direct, the default, keeps no mapping)` も出します（`engine/src/program/generate.cpp:12261-12271`）。
- 変数が設定されていると、これらの解除処理と対応する結果ログは出ません。変数自身についての警告、エラー、終了コード変更はありません。
- ソースコメントには Windows の PCIe 4 NVMe（WD SN580）で、2 MiB 読み取り・queue depth 32 の測定として、`experts.bin` をマップした状態 2.35 GB/s、マップ解除後 3.57 GB/s と記載されています。これは実装コメントの条件付き測定であり、他の機器やモデルでの速度を示すものではありません（`engine/include/strata/core/expert_source.hpp:928-935`）。

## 根拠

- `engine/src/program/generate.cpp:8621-8628,8654-8668` — FileExpertSource の選択、初回の非バッファ設定、Windows の検証付きマップ解除。
- `engine/src/program/generate.cpp:8745-8747,8871-8911,8972` — file source と arena source の選択・RAM 不足時の file fallback。
- `engine/src/program/generate.cpp:12108-12117,12259-12271` — startup 後の再判定、2回目のマップ解除、観測可能なログ。
- `engine/src/core/expert_source.cpp:959-972,2842-2858` — file tier の非バッファ読み取り判定と OS 条件。
- `engine/src/core/expert_source.cpp:2910-2961,3001-3029` — マップ解除の Windows 実装、Linux の本番外テスト分岐、初回解除前の照合。
- `engine/include/strata/core/expert_source.hpp:912-919,928-935` — 非バッファ読み取りとマップ解除の役割、および測定コメント。
