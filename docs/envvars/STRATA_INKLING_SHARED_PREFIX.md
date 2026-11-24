# `STRATA_INKLING_SHARED_PREFIX`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

## 役割

Inkling engine を使う serve の各リクエストで、先頭に連続する `system` / `developer` メッセージを共有 prefix として自動指定する opt-in です。Strata は request に `strata_prefix` がまだなく、engine が共有 checkpoint 対応を通知し、画像を含まない場合に限り、対象メッセージ数から token 境界を解決して `pin=<token数>` を engine の `GEN` 行へ加えます。サーバー起動時やモデル読込時に値を設定する変数ではなく、通常の prompt 内容・sampling 値・返信 token 数を直接変更しません（`terminal/serve/server.py:5524-5527, 5674-5706, 1380-1387, 2646-2653`）。

## 値と判定

`Service.prepare` 内で `os.environ.get(...) == "1"` と文字列全体を比較します。数値変換、trim、大文字小文字変換はありません。環境変数は `prepare` の呼び出しごとに読み直され、値を関数外や `static` に cache しません（`terminal/serve/server.py:5674-5677`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| serve の自動指定 | 自動指定なし | `1` のみ | 空文字、`0`、`true`、`TRUE`、` 1`、`1 `、`0anything` |

この変数が unset または無効値でも、API request が明示した `strata_prefix` は別経路で処理されます。request に `strata_prefix` キーが存在する場合（値が `null` でも）自動指定は行いません（`terminal/serve/server.py:5676-5677`）。

## 有効になる条件

- Serve が Inkling engine と判定した場合に限ります。判定は executable の basename が `strata-inkling` で始まることによります（`terminal/serve/server.py:769-771`; `terminal/serve/inkling_kind.py:10-12, 34-35`）。この変数の判定自体に OS 固有分岐はありません。
- engine の `INFO` にある `shared_prefix` を文字列化した値が厳密に `"1"` である必要があります。Strata の Inkling engine は backend の `supports_shared_checkpoint()` の結果を `shared_prefix` として通知します（`terminal/serve/server.py:860-863, 5675-5677`; `engine/src/inkling2/ink_serve.h:562-568`）。現行 CUDA backend では初期化済みで、layer split または ShortConv snapshot があり、slot 数が 8 以下の場合にこの capability を返します（`engine/src/inkling2/cuda/ink_cuda_backend.cu:413-415`）。基底 backend の既定は非対応です（`engine/src/inkling2/ink_backend.h:104-110`）。
- API request の辞書 `req` が必要です。通常の OpenAI chat、Responses、Anthropic の handler は request を `prepare` に渡します。一方 MCP tool loop 内の続きの `prepare` 呼び出しは `req` を渡さないため、自動指定されません（`terminal/serve/server.py:8238, 8478-8485, 8533, 6737-6739`）。
- prompt に画像がない必要があります。Inkling の画像入力を処理した場合も `had_images` は true のままなので、自動指定の条件を満たしません（`terminal/serve/server.py:5554-5570, 5676-5677`）。
- メッセージ列の先頭に 1 件以上の `system` / `developer` が連続し、その後に少なくとも 1 件の別 role のメッセージが必要です。全件が `system` / `developer` の場合、または先頭が別 role の場合は自動指定しません（`terminal/serve/server.py:5678-5686`）。
- `strata_prefix` は先頭 K メッセージを render/tokenize した結果と実 prompt の共通 token prefix として解決されます。解決後は engine の `chunk` が正なら token 数を chunk 単位で切り下げます。chunk が欠落・不正・0 以下なら自動境界は空になります（`terminal/serve/server.py:5694-5701, 5741-5759, 5761-5770`）。

## 実行時の詳細

環境変数は `Service.prepare` が各リクエストの prompt を encode した後に評価されます。自動指定条件を満たすとき、Strata は先頭の連続した system/developer message 数を `{ "messages": K }` として `resolve_prefix` に渡します。ここで境界の token 数を解決し、`pin` に使う `{"tokens": N}` へ変換します。chunk が正なら `N` を `floor(N / chunk) * chunk` に丸め、0 以下なら `{}` にします（`terminal/serve/server.py:5674-5701, 5711-5719`）。

Inkling 向け `sampling_keys` は解決済み token 数が正の整数なら `pin=N` を生成し、`StrataEngine.run` がそのキーを `GEN` または `GENI` 行に含めて常駐 engine へ送ります（`terminal/serve/server.py:1373-1387, 2646-2653`）。engine 側では指定 slot に共有 checkpoint が保存され、後続 request の token prefix が一致した場合に同じ slot で復元対象になります（`engine/src/inkling2/ink_serve.h:690-710, 1112-1117`）。他 slot へのコピーを Strata server が行う経路ではありません。

この環境変数は設定値を起動時に保存しないため、同一プロセス内でも `prepare` 実行時点の環境値を読みます。server 起動後の環境書き換えが次の request に反映されるかは、書き換え主体とプロセス環境の扱いによります。Strata の CLI 引数でこの環境変数を上書きする経路は確認できません。明示 `strata_prefix` は自動設定より優先されます（`terminal/serve/server.py:5676-5677`）。

## ログと測定値

この変数を `"1"` にして自動境界が空になっても、専用の理由ログは出ません。明示 `strata_prefix` を指定した request で、Inkling engine が `shared_prefix=1` を通知していない場合には、Strata は非空の解決結果に対して stdout に次を出し、値を空にします（`terminal/serve/server.py:5687-5692`）。

```text
[strata] strata_prefix ignored: this Inkling engine does not advertise shared_prefix=1
```

自動指定は capability がある場合にしか作られないため、この warning は自動指定の失敗理由を示すログではありません。測定値は記載しません。

## 根拠

- 環境値の直接参照、自動境界の条件と生成: `terminal/serve/server.py:5674-5686`
- capability 判定、明示 prefix の処理、chunk 丸め: `terminal/serve/server.py:5687-5701`
- Inkling 判定と INFO 取り込み: `terminal/serve/server.py:769-771, 860-863`; `terminal/serve/inkling_kind.py:34-35`
- token 境界の解決と `pin=` の生成・送信: `terminal/serve/server.py:5711-5784, 1335-1387, 2646-2653`
- capability 通知と CUDA backend 条件: `engine/src/inkling2/ink_serve.h:562-568`; `engine/src/inkling2/ink_backend.h:104-110`; `engine/src/inkling2/cuda/ink_cuda_backend.cu:413-420`
- prefix checkpoint の保存・復元経路: `engine/src/inkling2/ink_serve.h:690-710, 1112-1117`
- 関連資料との照合: `docs/RESEARCH_RUNS.md:43-56`。leading system/developer の自動指定と chunk 境界への丸めは実装と一致します。
