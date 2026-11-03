# `STRATA_ARENA_RAM_FALLBACK`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

expert arena を RAM に読み込む起動経路で、必要 RAM が足りない場合に、その起動だけ expert の読み出し元を `--mmap-experts` と同じファイル経路へ自動で切り替えるかを制御します。通常は既定で切替を許可します。`--mmap-experts` がすでに指定されている起動では arena の不足判定を使わないため、この変数による自動切替もありません。

この切替は起動を拒否する代わりにファイルから読む選択です。静的 expert profile があり、別の条件も満たす場合は、切替後に profile 上位 expert の一部を RAM に置く resident-budget 形式も自動で有効になります（後述）。

## 値と判定

`arena_ram_fallback_allowed()` は環境変数の値全体を検証せず、空でない値を `std::atoi()` に渡し、変換結果が 0 かどうかで判定します。

| 値 | 判定 |
|---|---|
| 未設定 | 許可 |
| 空文字 | 許可（未設定と同じ） |
| `0`、`00`、`0abc`、数値に変換できない文字列 | 不許可（`atoi` の結果が 0） |
| `1`、`-1`、`2x`、` 2` など、`atoi` の結果が非 0 | 許可 |

したがって厳密な `0` / `1` のみを受け付ける設定ではありません。小数や範囲の検証もありません。たとえば `0.5` は整数変換結果が 0 なので不許可です。無効な文字列をエラーにはせず、0 相当として自動切替を止めます。

## 有効になる条件

次の条件で自動切替が許可されます。

- 実行が arena を開く経路である。
- `--ple-io ram` が明示されていない。明示された場合、環境変数が非 0 でも自動切替しません。`--ple-io` の他の値や未指定は、この抑止条件には該当しません。
- `--shared-expert-arena` が指定されていない。
- 環境変数が未設定、空文字、または `atoi` の結果が非 0。

許可されても、arena が必要量の RAM を使える場合は切替を行いません。メモリ情報が取得できない場合も不足判定を通らず、通常の arena 読み込みを試みます。固定した選択を尊重する `--ple-io ram` と共有 arena は、この変数より優先されます。

不足判定では arena 本体と最大 blob 1 個分に `--ram-keep-gib` の指定量を加えて必要量を計算します。hard limit（cgroup 等）がある場合、切替許可時はさらに `max(--ram-keep-gib, headroom)` を limit 判定に加えます。headroom は通常 Windows 8 GiB、その他 4 GiB で、`STRATA_RESIDENT_HEADROOM_GIB` が有効な数値として指定されればその値に置き換わります。

## 実行時の詳細

値は generate の起動処理中、`ArenaExpertSource::open()` より前に読み取られ、1 回の起動中に判定結果が使われます。`static` cache ではありません。環境変数を変更しても、すでに起動したプロセスの判定は変わりません。CLI 引数がこの環境変数の値を設定する仕組みはありませんが、明示 `--ple-io ram` と共有 arena が自動 fallback を禁止します。

hard limit が不足していて切替可能なら、arena の割当て・登録を行わず `ram_short` を返し、呼び出し元が expert ファイル経路に切り替えます。通常の利用可能 RAM が足りない場合は、既定で最大 20 秒、`STRATA_ARENA_RAM_WAIT_S` の指定があればその範囲内の秒数だけ空きを待ちます。待機後も不足し、切替可能なら同じファイル経路へ切り替えます。切替不可のときは hard limit 不足で起動エラーになり、通常 RAM 不足は警告して arena 読み込みを続けます。

切替先を開けなかった場合、呼び出し元はそのエラーを出し、arena を従来どおり再試行します。この再試行では同じ RAM 不足による fallback を無効にします。2 回目も開けなければエラーを出して終了します。

切替成功時は stderr に `not enough RAM for the expert arena (...): this run reads the experts from the file, like --mmap-experts (slower; the answers are the same).` と出し、続いて `experts via mmap (not enough RAM for the expert arena: the same source as --mmap-experts; ...)` を出します。expert file source を開けない場合は追加で診断を出し、arena 再試行を行います。

profile が空でなく、既に resident CPU experts が有効でなく、かつ `STRATA_ARENA_FALLBACK_RESIDENT` の先頭文字が `0` でない場合は、切替後に profile 上位 expert を利用可能 RAM と headroom の範囲で resident RAM copy に置き、残りをファイルから読みます。`STRATA_ARENA_FALLBACK_RESIDENT=0...` はこの resident 化だけを止め、`STRATA_ARENA_RAM_FALLBACK` によるファイル経路への切替は止めません。

## 根拠

- 全参照の検索では本番読み取りは `src/program/generate.cpp:7072-7073` の一箇所です。`include/strata/core/ple_residency.hpp:65-72` の helper が優先条件、空文字、`atoi` 判定、既定許可を定義します。残る同名参照はコメントと `src/core/ple_residency_test.cpp:72-78` のテストです。
- `src/program/generate.cpp:3352` は `--ple-io` の明示状態を記録し、`src/program/generate.cpp:3645` は共有 arena 引数を受け取ります。判定結果の設定、fallback 状態、headroom は `src/program/generate.cpp:7065-7088,7306-7317` にあります。
- hard limit と RAM 必要量判定は `src/core/expert_source.cpp:5871-5900`、待機・ロック解放・不足時の fallback / 警告は `src/core/expert_source.cpp:5901-5968` にあります。判定に使う `arena + blob + ram_keep` は同ファイル `5874-5878`、helper は `include/strata/core/ple_residency.hpp:58-63,98-105` です。
- 切替後のファイル source 開始、open 失敗時の arena 再試行、resident RAM fallback とログは `src/program/generate.cpp:7091-7117,7321-7347` にあります。`STRATA_ARENA_FALLBACK_RESIDENT` の判定は `src/program/generate.cpp:7074-7075,7333-7341` です。
- `STRATA_ARENA_RAM_WAIT_S` の既定・変換範囲（全体を `strtod` で読み、0〜3600 秒）と待機ログは `src/core/expert_source.cpp:5906-5929` にあります。
- 関連する RAM 方針の説明は `docs/DETAILS.md:740-764` にあります。同資料の記述を超える性能値はこの文書では主張しません。
