# `STRATA_FS_DEPTH`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Foresight swap space の VRAM スロットを再利用するまでに待つ、完了済み verify window の数を決めます。値を大きくすると、直近の window が読み得るスロットをより長く保持します。ルーターの選択、コピー対象、またはモデルの出力を直接変える設定ではありません。スロットがまだ読み込み中・未着の場合はそのスロットを使わず、通常の miss 処理へ進みます（`engine/src/core/expert_source.cpp:7248-7259`、`engine/src/core/expert_source.cpp:5583-5606`）。

実装は `strata::core::foresight_swap_from_env()` で、`--serve` の生成経路が Foresight swap を作成し、verify/route 側に接続します（`engine/src/core/expert_source.cpp:7294-7321`、`engine/src/program/generate.cpp:14794-14815`）。

## 値と判定

`STRATA_FS_SLOTS` が正数で、デバイス側 plan/hits の検証モードで無効化されない場合に限り、この変数を読みます。読み取りは `getenv` の結果を `atoi` に渡し、未設定なら 4、変換値が 2 未満なら 2 に丸めます。上限の clamp はありません。`atoi` は整数の先頭部分を読むため、空文字や数字で始まらない値は 0 となり 2 に丸められます。数値の後ろの文字や先頭空白は変換を妨げず、符号も整数変換に含まれます。大文字小文字の概念はありません（`engine/src/core/expert_source.cpp:7306-7311`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---:|---|---|
| Foresight swap の初期化に進む場合 | 4 | 整数変換結果が 2 以上。例: `2`, `4`, `7`, `4tail` | 整数変換結果が 2 未満なら 2 として有効。例: `0`, `1`, `-3`, 空文字, `true` はいずれも 2 |
| `STRATA_FS_SLOTS` が未設定または `atoi` 結果 `<= 0` | 読まれない | 該当なし | Foresight swap 自体が作成されない |
| `STRATA_VERIFY_DEVICE_PLAN` または `STRATA_VERIFY_DEVICE_HITS` が設定され、`atoi` 結果が非 0 | 読まれない | 該当なし | Foresight swap 自体が無効化される |

CLI 引数や設定ファイルからこの値を上書きする処理は、この読み取り経路にはありません。`--pipeline-windows` は同時に進む window 数に関する別設定で、`STRATA_FS_DEPTH` の値を置き換えません（`engine/include/strata/core/foresight_swap.hpp:10-14`）。

## 有効になる条件

- `STRATA_FS_SLOTS` が設定され、`atoi` 結果が 1 以上であること。実際に確保する slot 数は最大 64 に制限されます（`engine/src/core/expert_source.cpp:7296-7298,7313`）。
- `STRATA_VERIFY_DEVICE_PLAN` と `STRATA_VERIFY_DEVICE_HITS` の両方が未設定または整数変換結果 0 であること。どちらかが非 0 なら swap space を無効にして理由を stderr に出します（`engine/src/core/expert_source.cpp:7299-7305`）。
- 初期化が成功すること。割り当て・CUDA event 作成の失敗時は swap space を無効にします（`engine/src/core/expert_source.cpp:7082-7108,7312-7316`）。
- コピーを発行するには、対象 expert が pin 済みで、その blob を取得でき、空きまたは再利用可能な slot があり、カードごとのコピー予算内である必要があります。これらを満たさない miss は slot にコピーされません（`engine/src/core/expert_source.cpp:7239-7261`）。
- 読み込み済み slot を GPU 側で使うのは、対象 expert が cache におらず、peer GPU や helper が処理せず、swap slot のコピーが完了している場合です。未着なら `take()` は false となり、通常の miss 処理へ進みます（`engine/src/core/expert_source.cpp:5583-5606,7161-7195`）。

## 実行時の詳細

serve の生成経路で `foresight_swap_from_env()` が呼ばれた時に値を読み、`ForesightSwap::depth` に保存します。関数の呼び出し後に環境を変更しても、このオブジェクトの値は再読込されません。ソース上、設定値のキャッシュ用 static はなく、呼び出しごとに環境を読みます（`engine/src/core/expert_source.cpp:7294-7311`）。

成功した slot 参照時に、その slot は現在の完了済み window 数 `completed` を `last_ref` に記録します。再利用候補になるのは `last_ref + depth <= completed` となった後です。serve の2つの window 完了経路が `completed` を加算します。したがって `2` は最後の参照から少なくとも2 window が完了するまで待ち、既定の `4` は少なくとも4 window 待ちます（`engine/src/core/expert_source.cpp:7192-7195,7248-7259`、`engine/src/program/generate.cpp:22303-22305,23017-23020`）。

`STRATA_FS_DEPTH` 自体に対する警告やエラー出力はありません。初期化成功時は stderr に `reuse after %d windows` を含む設定ログが出るため、clamp 後に使われる値を確認できます。`STRATA_FS_SLOTS` が無効ならこのログも出ません。device plan/hits による無効化では `strata serve: foresight swap: off beside STRATA_VERIFY_DEVICE_PLAN/HITS (the device would plan resident layers without the host)` と出ます。初期化失敗時は `strata serve: foresight swap: %s - swap space off`、コピー失敗時は `strata serve: foresight swap: a copy failed - swap space off` が stderr に出ます（`engine/src/core/expert_source.cpp:7301-7304,7313-7320,7151-7155`）。

この変数固有の測定値は、調査対象コードと確認した Strata 資料にはありません。`docs/DETAILS.md:1244,1695` は `STRATA_FS_SLOTS` の記述・測定で、`STRATA_FS_DEPTH` の比較結果ではありません。

## 根拠

- `engine/src/core/expert_source.cpp:7294-7321` — 環境値の読み取り、既定値 4、下限 2、初期化と設定ログ。
- `engine/src/core/expert_source.cpp:7248-7259` — `depth` による slot 再利用条件。
- `engine/src/program/generate.cpp:14794-14815,22303-22305,23017-23020` — serve 経路での生成・接続と完了 window 数の加算。
- `engine/src/core/expert_source.cpp:5583-5606,7161-7195` — landed slot の利用と未着時の通常 miss 経路。
- `engine/include/strata/core/foresight_swap.hpp:10-14` — slot 参照後の安全な再利用に関する実装コメント。
